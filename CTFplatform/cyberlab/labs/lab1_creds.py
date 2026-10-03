"""
Lab 1 — Leaky Backup File (Sensitive Information Disclosure)

v3: significantly harder than v2.
  - The backup directory now requires HTTP Basic Auth. The credentials
    aren't shown on the rendered page -- they're base64-encoded inside
    an HTML comment in the homepage's source (view-source required).
  - The listing (once authenticated) shows an EXPIRED backup plus a
    decoy expired backup with a plausible-but-wrong naming hint.
  - The real expired file's comment gives the true naming pattern, but
    the key word is ROT13-encoded, not plaintext -- you have to notice
    it's ROT13 and decode it.
  - The real production file is still never linked anywhere.
"""
import base64
from functools import wraps
from flask import Blueprint, render_template, request, Response

import progress

lab1_bp = Blueprint("lab1", __name__, template_folder="../templates/lab1")

ADMIN_USER = "sayali.admin"
ADMIN_PASS_CURRENT = "Tr!net_Ops#2026"
ADMIN_PASS_EXPIRED = "Summer2023!"
FLAG = "CYBERLAB{backups_are_not_hidden_theyre_just_unlinked}"

BASIC_AUTH_USER = "ops_readonly"
BASIC_AUTH_PASS = "B4ckup_View!"
BASIC_AUTH_B64 = base64.b64encode(f"{BASIC_AUTH_USER}:{BASIC_AUTH_PASS}".encode()).decode()


def require_basic_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != BASIC_AUTH_USER or auth.password != BASIC_AUTH_PASS:
            return Response(
                "Authentication required.", 401,
                {"WWW-Authenticate": 'Basic realm="Ops Backup Archive"'},
            )
        return f(*args, **kwargs)
    return wrapper


@lab1_bp.route("/")
def index():
    ctx = progress.lab_context("lab1")
    return render_template("lab1/index.html", auth_hint_b64=BASIC_AUTH_B64, **ctx)


@lab1_bp.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Disallow: /lab1/old_admin_panel/\n"
        "Disallow: /lab1/assets/\n"
        "Disallow: /lab1/backup/\n"
    )
    return body, 200, {"Content-Type": "text/plain"}


@lab1_bp.route("/old_admin_panel/")
def old_admin_panel():
    return (
        "<h3 style='font-family:sans-serif'>410 Gone</h3>"
        "<p style='font-family:sans-serif'>Decommissioned when we moved to the new ops portal.</p>",
        410,
    )


@lab1_bp.route("/assets/")
def assets_listing():
    return render_template("lab1/assets_listing.html")


@lab1_bp.route("/assets/ops-notes.js")
def assets_js():
    body = (
        "// TODO(tejas): minify this before launch\n"
        "console.log('ops dashboard v0.9 loaded');\n"
        "// unrelated to auth, this just toggles the dark theme\n"
        "function toggleTheme() { document.body.classList.toggle('dark'); }\n"
    )
    return body, 200, {"Content-Type": "application/javascript"}


@lab1_bp.route("/backup/")
@require_basic_auth
def backup_listing():
    progress.mark_explored("lab1")
    return render_template("lab1/backup_listing.html")


@lab1_bp.route("/backup/config_staging_2024.yaml.bak")
@require_basic_auth
def backup_decoy():
    # Decoy: plausible-looking, but a dead end -- no creds that work here,
    # and its "hint" deliberately points the wrong direction.
    content = (
        "# very old staging config, pre-migration\n"
        "# ayush: this predates the current environment naming scheme entirely,\n"
        "# not related to the current admin account setup\n"
        "app_env: staging-legacy\n"
        "note: decommissioned service, no active credentials here\n"
    )
    return content, 200, {"Content-Type": "text/plain"}


@lab1_bp.route("/backup/config_old.yaml.bak")
@require_basic_auth
def backup_file_expired():
    content = (
        "# staging config -- superseded, see migration notes below\n"
        "# migration completed by sumit, Aug 2026\n"
        "# renamed this file after rotating creds -- new one is NOT linked anywhere.\n"
        "# naming pattern: config_<env>_<year>.yaml.bak\n"
        "# env token for prod (rot13'd because I don't trust this listing): 'cebq'\n"
        "app_env: staging\n"
        "database:\n"
        "  host: localhost\n"
        "  port: 5432\n"
        "admin_account:\n"
        f"  username: {ADMIN_USER}\n"
        f"  password: {ADMIN_PASS_EXPIRED}\n"
        "  note: ROTATED -- this password no longer works.\n"
    )
    return content, 200, {"Content-Type": "text/plain"}


@lab1_bp.route("/backup/config_prod_2026.yaml.bak")
@require_basic_auth
def backup_file_current():
    content = (
        "# production config -- DO NOT SHARE\n"
        "app_env: production\n"
        "database:\n"
        "  host: db-prod.internal\n"
        "  port: 5432\n"
        "admin_account:\n"
        f"  username: {ADMIN_USER}\n"
        f"  password: {ADMIN_PASS_CURRENT}\n"
        "  note: current, rotate quarterly\n"
    )
    return content, 200, {"Content-Type": "text/plain"}


@lab1_bp.route("/login", methods=["GET", "POST"])
def login():
    progress.mark_explored("lab1")
    error = None
    success = False
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == ADMIN_USER and p == ADMIN_PASS_CURRENT:
            success = True
        elif u == ADMIN_USER and p == ADMIN_PASS_EXPIRED:
            error = "This password was rotated after the migration and no longer works."
        else:
            error = "Invalid username or password."
    return render_template("lab1/login.html", error=error, success=success, flag=FLAG)
