"""
CyberLab Sim — a small, local, beginner-friendly vulnerable-app playground.

5 self-contained labs, each recreating a real class of bug in a safe,
sandboxed way. Nothing here touches the real filesystem or OS outside
this project folder, and there is no real remote code execution —
"RCE" in Lab 5 is simulated so you can see the mechanism without any
actual danger.

Run:
    pip install -r requirements.txt
    python3 app.py
Then open http://127.0.0.1:5000

Configuration (see .env.example):
    SECRET_KEY   Flask session-signing key. Falls back to a clearly-
                 labeled, non-production dev key if unset -- see
                 README.md "Secret key" section before deploying this
                 anywhere beyond your own machine (which you shouldn't).
    FLASK_DEBUG  "1" to enable debug mode. Off by default.
    HOST         Interface to bind to. Defaults to 127.0.0.1.
"""
import os

try:
    # Optional convenience: if python-dotenv is installed and a .env
    # file exists, load it. Never required -- plain `export` works too.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

import progress
from redirect_safety import safe_redirect_target
from labs.lab_meta import (
    LAB_IDS,
    LAB_TITLES,
    DIFFICULTY,
    DIFFICULTY_CLASS,
    FLAGS,
    HINTS,
    SECURITY_INFO,
    LEARN_BEFORE,
    CODE_EXAMPLES,
    KEY_CONCEPTS,
    WRONG_ATTEMPT_TIPS,
    MODES,
    MODE_LABELS,
    MODE_HINT_CAP,
    LEARNING_ORDER,
)
from labs.lab1_creds import lab1_bp
from labs.lab2_sqli import lab2_bp
from labs.lab3_idor import lab3_bp
from labs.lab4_traversal import lab4_bp
from labs.lab5_deserialization import lab5_bp

app = Flask(__name__)

# --- Secret key -------------------------------------------------------
# Session cookies (progress, mode, hints) are signed with this. Set a
# real SECRET_KEY env var for anything beyond casual local use. The
# fallback below is intentionally obvious and documented -- it is a
# training tool's dev default, not a production secret, and should
# never be relied on outside your own machine.
_DEV_FALLBACK_SECRET_KEY = "dev-only-fallback-key-set-SECRET_KEY-env-var-for-real-use"
app.secret_key = os.environ.get("SECRET_KEY", _DEV_FALLBACK_SECRET_KEY)
if app.secret_key == _DEV_FALLBACK_SECRET_KEY:
    app.logger.warning(
        "SECRET_KEY is not set -- using an insecure development fallback. "
        "Set SECRET_KEY in your environment (see .env.example) before "
        "sharing this instance with anyone else, even on your LAN."
    )

app.register_blueprint(lab1_bp, url_prefix="/lab1")
app.register_blueprint(lab2_bp, url_prefix="/lab2")
app.register_blueprint(lab3_bp, url_prefix="/lab3")
app.register_blueprint(lab4_bp, url_prefix="/lab4")
app.register_blueprint(lab5_bp, url_prefix="/lab5")

LABS = [
    {
        "id": "lab1",
        "title": f"Lab 1 — {LAB_TITLES['lab1']}",
        "tagline": "Sensitive info disclosure via a forgotten backup file",
        "difficulty": DIFFICULTY["lab1"],
        "url": "/lab1/",
    },
    {
        "id": "lab2",
        "title": f"Lab 2 — {LAB_TITLES['lab2']}",
        "tagline": "SQL injection + account enumeration",
        "difficulty": DIFFICULTY["lab2"],
        "url": "/lab2/",
    },
    {
        "id": "lab3",
        "title": f"Lab 3 — {LAB_TITLES['lab3']}",
        "tagline": "Broken access control via a client-trusted cookie",
        "difficulty": DIFFICULTY["lab3"],
        "url": "/lab3/",
    },
    {
        "id": "lab4",
        "title": f"Lab 4 — {LAB_TITLES['lab4']}",
        "tagline": "Path traversal, filter-bypass required",
        "difficulty": DIFFICULTY["lab4"],
        "url": "/lab4/",
    },
    {
        "id": "lab5",
        "title": f"Lab 5 — {LAB_TITLES['lab5']}",
        "tagline": "Insecure deserialization (simulated RCE)",
        "difficulty": DIFFICULTY["lab5"],
        "url": "/lab5/",
    },
]


@app.context_processor
def inject_globals():
    # Available in every template without passing explicitly each time.
    return {
        "SECURITY_INFO_MAP": SECURITY_INFO,
        "DIFFICULTY_MAP": DIFFICULTY,
        "DIFFICULTY_CLASS_MAP": DIFFICULTY_CLASS,
        "LAB_TITLES_MAP": LAB_TITLES,
        "LEARN_BEFORE_MAP": LEARN_BEFORE,
        "CODE_EXAMPLES_MAP": CODE_EXAMPLES,
        "KEY_CONCEPTS_MAP": KEY_CONCEPTS,
        "MODES": MODES,
        "MODE_LABELS": MODE_LABELS,
        "current_mode": progress.get_mode(),
        "LABS_BY_ID": {l["id"]: l for l in LABS},
        "LEARNING_ORDER": LEARNING_ORDER,
    }


def _prev_next_lab(lab_id):
    """(previous_lab_dict_or_None, next_lab_dict_or_None) in the
    recommended learning order -- purely informational, never enforced."""
    by_id = {l["id"]: l for l in LABS}
    if lab_id not in LEARNING_ORDER:
        return None, None
    idx = LEARNING_ORDER.index(lab_id)
    prev_lab = by_id.get(LEARNING_ORDER[idx - 1]) if idx > 0 else None
    next_lab = by_id.get(LEARNING_ORDER[idx + 1]) if idx < len(LEARNING_ORDER) - 1 else None
    return prev_lab, next_lab


@app.route("/")
def home():
    prog = progress.get_progress()
    return render_template("home.html", labs=LABS, prog=prog, overall=progress.overall_percentage())


def _recommended_next_lab(prog):
    """First not-yet-completed lab in learning order, or None if all done."""
    for lab_id in LEARNING_ORDER:
        if not prog.get(lab_id, {}).get("completed"):
            return lab_id
    return None


@app.route("/health")
def health():
    """Simple liveness check -- used by Docker Compose's healthcheck and
    useful for verifying the app is up before pointing a browser/proxy
    at it. Deliberately returns no session or progress data."""
    return jsonify(status="ok", service="cyberlab")


@app.route("/dashboard")
def dashboard():
    prog = progress.get_progress()
    labs_completed = progress.labs_completed_count()
    total_score = progress.total_score()
    total_hints_used = progress.total_hints_used()
    max_possible = progress.max_possible_score()
    recommended = _recommended_next_lab(prog)
    return render_template(
        "dashboard.html",
        labs=LABS,
        prog=prog,
        overall=progress.overall_percentage(),
        labs_completed=labs_completed,
        total_labs=len(LAB_IDS),
        total_score=total_score,
        max_possible=max_possible,
        total_hints_used=total_hints_used,
        recommended_lab=next((l for l in LABS if l["id"] == recommended), None),
        achievements=progress.get_achievements(),
    )


@app.route("/mode", methods=["POST"])
def set_mode_route():
    mode = request.form.get("mode", "")
    next_url = safe_redirect_target(request.form.get("next"), default=url_for("home"))
    progress.set_mode(mode)
    flash(f"Learning mode set to: {MODE_LABELS.get(progress.get_mode(), progress.get_mode())}", "success")
    return redirect(next_url)


@app.route("/burp-guide")
def burp_guide():
    return render_template("burp_guide.html")


@app.route("/stage/<lab_id>/identify", methods=["POST"])
def stage_identify_route(lab_id):
    """Explicit student self-report: 'I understand the vulnerability I
    found.' Intentionally NOT triggered automatically by hint usage --
    see progress.mark_identified for why."""
    next_url = safe_redirect_target(request.form.get("next"), default=url_for("home"))
    if lab_id in LAB_IDS:
        progress.mark_identified(lab_id)
    return redirect(next_url + "#stages")


@app.route("/stage/<lab_id>/remediation", methods=["POST"])
def stage_remediation_route(lab_id):
    """Marks 'Learn the remediation' when the student actually opens the
    security writeup -- only meaningful once the lab is completed."""
    next_url = safe_redirect_target(request.form.get("next"), default=url_for("home"))
    if lab_id in LAB_IDS:
        progress.mark_remediation_viewed(lab_id)
    return redirect(next_url + "#writeup")


@app.route("/submit-flag", methods=["POST"])
def submit_flag_route():
    lab_id = request.form.get("lab_id", "")
    flag = request.form.get("flag", "")
    next_url = safe_redirect_target(request.form.get("next"), default=url_for("home"))

    if lab_id not in FLAGS:
        flash("Unknown lab selected.", "error")
        return redirect(next_url)

    correct = progress.submit_flag(lab_id, flag, FLAGS[lab_id])
    if correct:
        flash(f"✅ Correct flag for {LAB_TITLES[lab_id]}! Lab marked complete.", "success")
    else:
        tip = WRONG_ATTEMPT_TIPS.get(lab_id, "")
        msg = "❌ Incorrect flag. Keep trying."
        if tip:
            msg += f" {tip}"
        flash(msg, "error")
    return redirect(next_url)


@app.route("/hint/<lab_id>/<int:level>", methods=["POST"])
def hint_route(lab_id, level):
    next_url = safe_redirect_target(request.form.get("next"), default=url_for("home"))
    if lab_id not in HINTS or not (1 <= level <= len(HINTS[lab_id])):
        return redirect(next_url)
    cap = MODE_HINT_CAP.get(progress.get_mode(), len(HINTS[lab_id]))
    if level > cap:
        flash("Your current learning mode limits how many hints are available. Switch to Beginner or Normal mode for more.", "error")
        return redirect(next_url + "#hints")
    current = progress.get_progress()[lab_id]["hints_used"]
    if level > current:
        progress.use_hint(lab_id)
    return redirect(next_url + "#hints")


@app.route("/reset/<lab_id>", methods=["POST"])
def reset_route(lab_id):
    next_url = safe_redirect_target(request.form.get("next"), default=url_for("home"))
    if lab_id in LAB_IDS:
        progress.reset_lab(lab_id)
        flash(f"{LAB_TITLES[lab_id]} progress reset.", "success")
    return redirect(next_url)


if __name__ == "__main__":
    import os
    # Defaults to localhost-only. Docker sets HOST=0.0.0.0 so the port
    # mapping in docker-compose.yml (itself bound to 127.0.0.1 on the
    # host) can reach it -- see docker-compose.yml.
    host = os.environ.get("HOST", "127.0.0.1")
    # Debug mode is OFF by default -- safe for local training even if
    # someone forgets to change it. Opt in explicitly with FLASK_DEBUG=1
    # while actively developing this project.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host=host, port=5000)
