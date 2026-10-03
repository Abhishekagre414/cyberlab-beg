import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from config import get_config
from extensions import csrf, limiter, db, migrate
from flask_talisman import Talisman
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
import redis
import logging
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

load_dotenv()

# Configure basic logging (can be expanded to JSON formatter)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Sentry if DSN is provided
sentry_dsn = os.environ.get("SENTRY_DSN")
if os.environ.get('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,
    )

app = Flask(__name__)
app.config.from_object(get_config())

# Behind Vercel / nginx / any load balancer the app only ever sees plain HTTP
# from the proxy. Without ProxyFix, request.is_secure is False, so Talisman's
# HTTPS redirect loops forever, url_for(_external=True) builds http:// links
# and the real client IP is lost (breaking the per-IP rate limiter).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

csrf.init_app(app)
limiter.init_app(app)
logger.info(f"Rate limiter storage backend: {app.config.get('RATELIMIT_STORAGE_URI')}")

# Set up Redis for sessions ONLY when a Redis server is actually configured
# and reachable. The old code switched to Redis whenever FLASK_ENV=production
# and fell back to the docker-compose hostname `redis:6379`; on any host
# without that service (Vercel, Render, a plain VPS...) every request that
# touched the session then crashed with "Error connecting to redis:6379".
def _init_sessions(flask_app):
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        logger.info("REDIS_URL not set - using signed cookie sessions.")
        return
    try:
        client = redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
        client.ping()  # fail now (and fall back), not on the first user request
        flask_app.config['SESSION_TYPE'] = 'redis'
        flask_app.config['SESSION_PERMANENT'] = False
        flask_app.config['SESSION_USE_SIGNER'] = True
        flask_app.config['SESSION_REDIS'] = client
        Session(flask_app)
        logger.info("Redis session management initialized.")
    except Exception as e:
        logger.warning("Redis unreachable (%s). Falling back to cookie sessions.", e)


_init_sessions(app)

# Strict Content-Security-Policy.
# * No 'unsafe-inline' for scripts: inline <script> blocks carry a per-request
#   nonce (Talisman exposes csp_nonce() to templates) and there are no inline
#   event handlers anywhere (they use data-click / data-action instead).
# * 'unsafe-inline' remains for *styles* only, because templates use style=""
#   attributes widely; that is a much smaller risk than inline scripts.
csp = {
    'default-src': ["'self'"],
    'script-src': ["'self'"],
    'style-src': ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com'],
    'font-src': ["'self'", 'https://fonts.gstatic.com', 'data:'],
    'img-src': ["'self'", 'data:'],
    'connect-src': ["'self'"],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    # Lab targets run on localhost ports and are shown in the virtual browser.
    'frame-src': ["'self'", 'http://localhost:*', 'http://127.0.0.1:*']
                 + ([f"http://{app.config['LAB_PUBLIC_HOST']}:*"] if app.config.get('LAB_PUBLIC_HOST') not in (None, '', '127.0.0.1') else []),
}
Talisman(
    app,
    content_security_policy=csp,
    content_security_policy_nonce_in=['script-src'],
    force_https=app.config.get('FORCE_HTTPS', False),
    # Talisman defaults this to True regardless of our own config, which
    # would force the `Secure` flag onto the session cookie even when
    # nothing in front of this app actually terminates TLS - browsers then
    # silently refuse to store the cookie at all, so every request looks
    # like a fresh, logged-out session. Tie it to the same flag as above.
    session_cookie_secure=app.config.get('SESSION_COOKIE_SECURE', False),
    # Don't pin browsers to HTTPS via HSTS unless HTTPS is deliberately forced.
    strict_transport_security=bool(app.config.get('FORCE_HTTPS', False)),
)

db.init_app(app)
import models  # noqa: F401 # Ensure models are loaded before migrate
migrate.init_app(app, db)




from routes.admin import admin_bp
from routes.leaderboard import leaderboard_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.labs import labs_bp
from routes.api import api_bp
from routes.pages import pages_bp


app.register_blueprint(admin_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(labs_bp)
app.register_blueprint(api_bp)
app.register_blueprint(pages_bp)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    try:
        db.session.rollback()
    except Exception:
        pass
    try:
        return render_template('errors/500.html'), 500
    except Exception:
        # The error page itself failed (e.g. DB down) - never recurse.
        return "500 - Internal Server Error", 500

_db_ready = False


def init_db():
    """Create tables and seed data. Idempotent and safe to call from several
    workers/instances at once (a lost race on the seed insert is ignored)."""
    global _db_ready
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        # create_all safely ignores existing tables
        db.create_all()
        _ensure_uploaded_labs_sort_order_column()
        _ensure_case_insensitive_username_index()
        # Seed only if admin doesn't exist
        if not models.User.query.filter_by(username='admin').first():
            logger.info("Initializing database with SQLAlchemy seed...")
            import seed_db
            try:
                seed_db.seed_database()
            except IntegrityError:
                # Another worker/instance seeded at the same moment.
                db.session.rollback()

        # Always runs: only inserts the CyberLab challenge rows that are
        # missing, so it's safe on every startup.
        import seed_cyberlab_challenges
        try:
            seed_cyberlab_challenges.seed_cyberlab_challenges()
        except IntegrityError:
            db.session.rollback()

    # Ensure upload directories exist (never fatal: read-only FS on some hosts)
    upload_dir = app.config.get('LAB_UPLOAD_DIR', os.path.join(os.path.dirname(__file__), 'data', 'uploaded_labs'))
    try:
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"Lab upload directory: {upload_dir}")
    except OSError as e:
        logger.warning(f"Could not create lab upload directory {upload_dir}: {e}")
    _db_ready = True


# MAX_CONTENT_LENGTH has to allow 100 MB lab uploads, but only the admin upload
# routes need that. Everything else (including unauthenticated endpoints)
# gets a small cap so nobody can make workers swallow huge request bodies.
_DEFAULT_BODY_LIMIT = int(os.environ.get('DEFAULT_MAX_BODY_BYTES', 2 * 1024 * 1024))


@app.before_request
def _limit_body_size():
    length = request.content_length
    if length is not None and length > _DEFAULT_BODY_LIMIT and not request.path.startswith('/admin/'):
        return jsonify({'success': False, 'message': 'Request body too large.'}), 413


@app.before_request
def _lazy_init_db():
    """Previously init_db() only ran under `python app.py`, so under gunicorn
    or Vercel the tables were never created and every DB query returned a
    500. Initialise once per process on the first real request.

    Set AUTO_INIT_DB=false when an entrypoint already runs init_db() (the
    Docker image does this so 4 gunicorn workers don't race)."""
    global _db_ready
    if _db_ready or os.environ.get('AUTO_INIT_DB', 'true').lower() == 'false':
        return
    if request.endpoint == 'static':
        return
    try:
        init_db()
    except Exception:
        logger.exception("Database initialisation failed")
        _db_ready = False


def _ensure_case_insensitive_username_index():
    """Enforce one account per case-insensitive username at the DB level.

    If an existing database already holds names that differ only by case, the
    index can't be built; log it and carry on (app-level checks still apply).
    """
    from sqlalchemy import text
    try:
        with db.engine.begin() as conn:
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_lower '
                              'ON users (lower(username))'))
    except Exception as e:
        logger.warning("Could not create case-insensitive username index "
                       "(duplicate names differing only by case?): %s", e)


def _ensure_uploaded_labs_sort_order_column():
    """db.create_all() only creates missing tables, not new columns on
    tables that already exist. Deployments upgrading from before labs had
    a learning-path order need this column added and backfilled once."""
    from sqlalchemy import inspect as sa_inspect, text

    inspector = sa_inspect(db.engine)
    if 'uploaded_labs' not in inspector.get_table_names():
        return
    existing_columns = {c['name'] for c in inspector.get_columns('uploaded_labs')}
    if 'sort_order' in existing_columns:
        return

    logger.info("Adding sort_order column to uploaded_labs and backfilling by creation date...")
    with db.engine.begin() as conn:
        conn.execute(text('ALTER TABLE uploaded_labs ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0'))
        rows = conn.execute(text('SELECT id FROM uploaded_labs ORDER BY created_at ASC')).fetchall()
        for i, row in enumerate(rows, start=1):
            conn.execute(text('UPDATE uploaded_labs SET sort_order = :n WHERE id = :id'),
                         {'n': i, 'id': row[0]})

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/health')
def health_check():
    """Simple health check endpoint for load balancers."""
    try:
        # Check DB connection
        db.session.execute(db.text('SELECT 1'))
        db_status = "ok"
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_status = "error"
        
    return jsonify({
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status
    }), 200 if db_status == "ok" else 503





if __name__ == '__main__':
    init_db()
    app.run(debug=app.config['DEBUG'], port=5000)
