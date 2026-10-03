import os
import shutil
from dotenv import load_dotenv
import secrets

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Vercel (and AWS Lambda style hosts) run the app on a READ-ONLY filesystem
# where only /tmp is writable, and every request may land on a different,
# short-lived instance. Detect it once so the rest of the config can adapt.
IS_SERVERLESS = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
WRITABLE_DIR = '/tmp' if IS_SERVERLESS else BASE_DIR


def _normalize_db_url(url):
    """Heroku/Neon/Supabase style URLs use the legacy `postgres://` scheme
    which SQLAlchemy 1.4+ rejects with 'Can't load plugin: postgres'."""
    if url and url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url


def _resolve_sqlite_path():
    """SQLite file location. On serverless the bundled DB is read-only, so
    copy it into /tmp once per instance and use the copy."""
    bundled = os.path.join(BASE_DIR, 'database', 'hacktheai.db')
    if not IS_SERVERLESS:
        return bundled
    target = os.path.join('/tmp', 'hacktheai.db')
    if not os.path.exists(target):
        try:
            if os.path.exists(bundled):
                shutil.copyfile(bundled, target)
        except OSError as e:
            print(f"WARNING: could not copy bundled DB to {target}: {e}")
    return target


def _get_or_create_persistent_secret_key():
    """Resolve SECRET_KEY, falling back to a value persisted on disk
    instead of a fresh random one every time.

    A brand-new random key on every process start breaks every existing
    session and CSRF token the instant the process restarts - and with
    multiple worker processes (e.g. `gunicorn --workers 4`), each worker
    would generate its OWN key independently, so a session created by one
    worker fails validation the moment a later request lands on a
    different worker. That looks exactly like sessions expiring within
    seconds and being logged out on refresh, for no obvious reason.

    An explicit SECRET_KEY environment variable always wins (this is what
    real production deployments should set). Without one, we generate a
    key once and store it under database/ so every worker/process/restart
    on this install reuses the same value.
    """
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    if IS_SERVERLESS:
        # Read-only FS + many short-lived instances: a generated key can never
        # be shared between instances, so sessions/CSRF would randomly fail.
        print("WARNING: SECRET_KEY is not set. On Vercel you MUST set it in "
              "Project Settings -> Environment Variables, otherwise logins "
              "will randomly fail between requests.")
        return secrets.token_hex(32)

    key_path = os.path.join(BASE_DIR, 'database', '.secret_key')
    try:
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                existing = f.read().strip()
            if existing:
                return existing
    except OSError:
        pass

    new_key = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        # Exclusive create so a race between multiple workers starting at
        # once can't have one worker overwrite another's freshly-written key.
        fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(new_key)
        print("WARNING: SECRET_KEY not set in environment. Generated one and "
              f"saved it to {key_path} so it persists across restarts. "
              "Set the SECRET_KEY environment variable explicitly for real deployments.")
        return new_key
    except FileExistsError:
        # Another worker won the race and wrote it first - read what it wrote.
        with open(key_path, 'r') as f:
            return f.read().strip()
    except OSError as e:
        print(f"WARNING: Could not persist SECRET_KEY to {key_path} ({e}). "
              "Using an ephemeral key. Sessions will be lost on restart. "
              "Set the SECRET_KEY environment variable explicitly!")
        return new_key


class Config:
    """Base configuration."""
    SECRET_KEY = _get_or_create_persistent_secret_key()

    # Database
    DATABASE_PATH = _resolve_sqlite_path()
    # Default to SQLite for local dev, override with PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    ) or f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    if IS_SERVERLESS and not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):
        print("WARNING: running serverless on a throw-away SQLite file in /tmp. "
              "Accounts and progress will vanish between instances. "
              "Set DATABASE_URL to a hosted Postgres database.")
    
    # Tuning for connection pooling under load
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,   # survive idle connections dropped by the DB
    }
    if not SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        if IS_SERVERLESS:
            # One tiny pool per lambda instance; hundreds of instances x 20
            # connections would exhaust a managed Postgres instantly.
            SQLALCHEMY_ENGINE_OPTIONS["pool_size"] = 1
            SQLALCHEMY_ENGINE_OPTIONS["max_overflow"] = 2
        else:
            SQLALCHEMY_ENGINE_OPTIONS["pool_size"] = 20
            SQLALCHEMY_ENGINE_OPTIONS["max_overflow"] = 10
    
    # Rate Limiting
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per day, 50 per hour")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", os.environ.get("REDIS_URL", "memory://"))

    # CSRF tokens default to expiring after 1 hour (Flask-WTF's WTF_CSRF_TIME_LIMIT),
    # which is the same length as a lab session. A learner who spends a while
    # working through a multi-step lab before submitting their flag would get a
    # silently-expired token: the request fails with a generic-looking error that
    # has nothing to do with the flag itself. Tying token validity to the login
    # session instead (no fixed time limit) avoids that entirely.
    WTF_CSRF_TIME_LIMIT = None

    # Secure Cookie settings. Forcing `Secure` on the session cookie when the
    # app isn't actually served over HTTPS makes browsers silently refuse to
    # store it at all - every request then looks like a brand new, logged-out
    # session. This must only turn on when the deployment genuinely terminates
    # TLS somewhere in front of it (set FORCE_HTTPS=true once that's true).
    FORCE_HTTPS = os.environ.get('FORCE_HTTPS', 'false').lower() == 'true'
    # Vercel always serves over HTTPS (TLS is terminated at their edge and
    # HTTP is redirected there), so Secure cookies are safe and correct.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 8 * 60 * 60  # 8 hours
    SESSION_COOKIE_SECURE = FORCE_HTTPS or IS_SERVERLESS

    # Lab Engine Config (previously only defined on DevelopmentConfig, so
    # production silently ran with different/missing limits).
    LAB_UPLOAD_MAX_SIZE = 100 * 1024 * 1024  # 100MB
    LAB_UPLOAD_DIR = os.path.join(WRITABLE_DIR, 'data', 'uploaded_labs')
    # Where learners' browsers reach lab containers. Defaults are loopback-only
    # (safe): set LAB_BIND_ADDR=0.0.0.0 and LAB_PUBLIC_HOST=<server name/IP> to
    # let remote learners connect (then firewall ports 10000-20000 to them only).
    LAB_PUBLIC_HOST = os.environ.get('LAB_PUBLIC_HOST') or '127.0.0.1'
    LAB_BIND_ADDR = os.environ.get('LAB_BIND_ADDR') or '127.0.0.1'
    LAB_CONTAINER_PORT_MIN = 10000
    LAB_CONTAINER_PORT_MAX = 20000
    LAB_SESSION_TIMEOUT = 3600  # 1 hour in seconds
    LAB_MAX_CONCURRENT_SESSIONS = 50
    LAB_MAX_ZIP_DECOMPRESSED_SIZE = 500 * 1024 * 1024  # 500MB
    LAB_MAX_ZIP_FILE_COUNT = 10000
    MAX_CONTENT_LENGTH = LAB_UPLOAD_MAX_SIZE

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # In dev, we might not have HTTPS
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # Only actually forces Secure cookies / HTTPS redirects when the
    # deployment has set FORCE_HTTPS=true (see Config.FORCE_HTTPS above).
    # Defaulting this to True unconditionally breaks any production
    # deployment that doesn't yet have TLS terminated in front of it
    # (e.g. the bundled nginx config, which ships with its HTTPS server
    # block commented out until certs are mounted).
    SESSION_COOKIE_SECURE = Config.FORCE_HTTPS or IS_SERVERLESS
    # Ensure SECRET_KEY is strictly enforced in production in the future.

config_by_name = dict(
    development=DevelopmentConfig,
    production=ProductionConfig,
    default=ProductionConfig
)

def _enforce_production_requirements(cfg):
    """Refuse to boot a multi-worker production server with per-process rate limits.

    With `memory://` every gunicorn worker keeps its own counters, so "5 per
    minute" on /login really means 5 x workers. A shared store (Redis) is
    required. Serverless hosts are exempt (they warn instead - instances are
    short-lived and a Redis is optional there); set
    ALLOW_MEMORY_RATELIMIT=true to knowingly override on a single-worker box.
    """
    if cfg is not ProductionConfig or IS_SERVERLESS:
        return
    if os.environ.get('ALLOW_MEMORY_RATELIMIT', 'false').lower() == 'true':
        return
    uri = (cfg.RATELIMIT_STORAGE_URI or '').lower()
    if uri.startswith('memory://'):
        raise RuntimeError(
            "Production requires a shared rate-limit store. Set REDIS_URL "
            "(or RATELIMIT_STORAGE_URI) to a Redis URL, or set "
            "ALLOW_MEMORY_RATELIMIT=true if you run exactly ONE worker."
        )


def get_config():
    env = os.environ.get('FLASK_ENV') or ('production' if IS_SERVERLESS else 'development')
    cfg = config_by_name.get(env, config_by_name['default'])
    _enforce_production_requirements(cfg)
    return cfg
