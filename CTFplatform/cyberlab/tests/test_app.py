"""
Automated tests for CyberLab Sim.

Run with:
    cd cyberlab
    pip install pytest --break-system-packages   # if needed
    python3 -m pytest tests/ -v

These cover the platform-level features (flags, progress, hints, reset,
instructor separation) and one representative vulnerable-behavior check
per lab so a refactor can't silently break the exploit path.
"""
import base64
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import app as flask_app
from labs.lab_meta import FLAGS


@pytest.fixture
def client():
    """Fresh Flask test client (and therefore a fresh, empty cookie jar)
    for every single test function. Because Flask's session lives
    entirely in a signed cookie, a client with no cookies sent yet has
    no session -- this is what gives us test isolation, verified by
    test_sessions_are_isolated_between_tests below. No prior test's
    progress, score, hints, mode, or completion state can leak in."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------
# 1. Application starts / all lab pages load
# ---------------------------------------------------------------------

def test_home_loads(client):
    r = client.get("/")
    assert r.status_code == 200


def test_dashboard_loads(client):
    r = client.get("/dashboard")
    assert r.status_code == 200


@pytest.mark.parametrize("lab_id", ["lab1", "lab2", "lab3", "lab4", "lab5"])
def test_lab_index_loads(client, lab_id):
    r = client.get(f"/{lab_id}/")
    assert r.status_code == 200


# ---------------------------------------------------------------------
# 2. Flag submission: correct accepted, incorrect rejected
# ---------------------------------------------------------------------

@pytest.mark.parametrize("lab_id", ["lab1", "lab2", "lab3", "lab4", "lab5"])
def test_incorrect_flag_rejected(client, lab_id):
    r = client.post(
        "/submit-flag",
        data={"lab_id": lab_id, "flag": "CYBERLAB{not_the_right_flag}", "next": f"/{lab_id}/"},
        follow_redirects=True,
    )
    assert "Incorrect flag" in r.get_data(as_text=True)


@pytest.mark.parametrize("lab_id", ["lab1", "lab2", "lab3", "lab4", "lab5"])
def test_correct_flag_accepted_and_marks_complete(client, lab_id):
    r = client.post(
        "/submit-flag",
        data={"lab_id": lab_id, "flag": FLAGS[lab_id], "next": f"/{lab_id}/"},
        follow_redirects=True,
    )
    body = r.get_data(as_text=True)
    assert "Correct flag" in body

    dash = client.get("/dashboard").get_data(as_text=True)
    assert "Completed" in dash


# ---------------------------------------------------------------------
# 3. Reset works
# ---------------------------------------------------------------------

def test_reset_clears_completion(client):
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    client.post("/reset/lab1", data={"next": "/lab1/"}, follow_redirects=True)
    dash = client.get("/dashboard").get_data(as_text=True)
    # lab1's row should now show Not Started -- can't easily isolate per-row
    # with a plain substring check, so assert score/points reset via the
    # lab page itself instead (no security writeup should show pre-completion).
    lab1_page = client.get("/lab1/").get_data(as_text=True)
    assert "CWE-200" not in lab1_page


def test_reset_clears_hints(client):
    client.post("/hint/lab2/1", data={"next": "/lab2/"})
    client.post("/hint/lab2/2", data={"next": "/lab2/"})
    client.post("/reset/lab2", data={"next": "/lab2/"})
    body = client.get("/lab2/").get_data(as_text=True)
    assert "0/3 used" in body


# ---------------------------------------------------------------------
# 4. Hints: progressive reveal, capped at 3, no skipping ahead scoring
# ---------------------------------------------------------------------

def test_hints_reveal_progressively(client):
    r1 = client.post("/hint/lab1/1", data={"next": "/lab1/"}, follow_redirects=True).get_data(as_text=True)
    assert "1/3 used" in r1
    r2 = client.post("/hint/lab1/2", data={"next": "/lab1/"}, follow_redirects=True).get_data(as_text=True)
    assert "2/3 used" in r2


def test_hints_are_post_only(client):
    # GET should no longer work now that hints/reset are state-changing
    # actions restricted to POST (see improvement #9, HTTP method review).
    r = client.get("/hint/lab1/1?next=/lab1/")
    assert r.status_code == 405
    r = client.get("/reset/lab1?next=/lab1/")
    assert r.status_code == 405


def test_hint_penalty_reduces_score(client):
    client.post("/hint/lab1/1", data={"next": "/lab1/"})
    client.post("/hint/lab1/2", data={"next": "/lab1/"})
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    dash = client.get("/dashboard").get_data(as_text=True)
    # 2 hints used -> 100 - 2*10 = 80
    assert "80/100" in dash


def test_challenge_mode_caps_hints(client):
    client.post("/mode", data={"mode": "challenge", "next": "/lab1/"})
    client.post("/hint/lab1/1", data={"next": "/lab1/"})
    r = client.post("/hint/lab1/2", data={"next": "/lab1/"}, follow_redirects=True)
    body = r.get_data(as_text=True)
    # Level 2 should be refused in challenge mode (cap is 1)
    assert "0/3 used" not in body  # level 1 still unlocked
    assert "1/3 used" in body
    assert "2/3 used" not in body


# ---------------------------------------------------------------------
# 5. Student cannot access instructor solutions via any web route
# ---------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/instructor/SOLUTIONS.md",
    "/SOLUTIONS.md",
    "/instructor/",
])
def test_instructor_solutions_not_web_reachable(client, path):
    r = client.get(path)
    assert r.status_code == 404


# ---------------------------------------------------------------------
# 6. Expected vulnerable behavior works for each lab (regression guard)
# ---------------------------------------------------------------------

def test_lab1_backup_requires_basic_auth(client):
    r = client.get("/lab1/backup/")
    assert r.status_code == 401


def test_lab1_full_chain(client):
    creds = base64.b64encode(b"ops_readonly:B4ckup_View!").decode()
    r = client.get("/lab1/backup/config_prod_2026.yaml.bak", headers={"Authorization": f"Basic {creds}"})
    assert "Tr!net_Ops#2026" in r.get_data(as_text=True)
    r = client.post("/lab1/login", data={"username": "sayali.admin", "password": "Tr!net_Ops#2026"})
    assert FLAGS["lab1"] in r.get_data(as_text=True)


def test_lab2_sqli_bypass_with_comment_filter_active(client):
    # plain "--" is filtered -- should NOT work
    r = client.post("/lab2/login", data={"username": "root_ops' --", "password": "x"})
    assert FLAGS["lab2"] not in r.get_data(as_text=True)
    # unclosed /* comment still works
    r = client.post("/lab2/login", data={"username": "root_ops'/*", "password": "x"})
    assert FLAGS["lab2"] in r.get_data(as_text=True)


def test_lab3_authorization_enforced_then_bypassed(client):
    client.get("/lab3/")
    denied = client.get("/lab3/invoice/4090")
    assert denied.status_code == 403
    client.set_cookie("x_client_user_id", "4090", domain="localhost")
    allowed = client.get("/lab3/invoice/4090", headers={"Cookie": "x_client_user_id=4090"})
    assert allowed.status_code == 200
    assert "an_id_in_the_url_" in allowed.get_data(as_text=True)


def test_lab4_naive_filter_blocked_then_bypassed(client):
    blocked = client.get("/lab4/download?file=../hr_confidential/ops_review_sayali.txt")
    assert FLAGS["lab4"] not in blocked.get_data(as_text=True)
    bypassed = client.get("/lab4/download?file=....//hr_confidential/ops_review_sayali.txt")
    assert FLAGS["lab4"] in bypassed.get_data(as_text=True)


def test_lab5_keyword_filter_blocked_then_bypassed(client):
    blocked = client.post(
        "/lab5/import",
        data={"yaml_input": 'cmd: !!python/object/apply:os.system ["cat flag.txt"]'},
    )
    assert "Blocked" in blocked.get_data(as_text=True)
    bypassed = client.post(
        "/lab5/import",
        data={"yaml_input": 'cmd: !!python/object/apply:posix.system ["cat flag.txt"]'},
    )
    assert FLAGS["lab5"] in bypassed.get_data(as_text=True)


# ---------------------------------------------------------------------
# 7. No unintended routes expose sensitive files
# ---------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/app.py",
    "/progress.py",
    "/labs/lab_meta.py",
    "/../etc/passwd",
])
def test_source_files_not_web_reachable(client, path):
    r = client.get(path)
    assert r.status_code in (404, 400)


# ---------------------------------------------------------------------
# 8. Learning mode selection
# ---------------------------------------------------------------------

def test_default_mode_is_normal(client):
    body = client.get("/lab1/").get_data(as_text=True)
    assert "Normal — standard hints" in body


@pytest.mark.parametrize("mode", ["beginner", "normal", "challenge"])
def test_mode_can_be_set_and_persists(client, mode):
    client.post("/mode", data={"mode": mode, "next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    assert f'value="{mode}" selected' in body


def test_beginner_mode_shows_learn_before_and_stages(client):
    client.post("/mode", data={"mode": "beginner", "next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    assert "Learn Before You Hack" in body
    assert "Your learning stages" in body


def test_challenge_mode_hides_extra_guidance(client):
    client.post("/mode", data={"mode": "challenge", "next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    assert "Learn Before You Hack" not in body
    assert "Why this happens in the real world" not in body


def test_invalid_mode_ignored(client):
    r = client.post("/mode", data={"mode": "godmode", "next": "/lab1/"}, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "Normal — standard hints" in body


# ---------------------------------------------------------------------
# 9. Dashboard shows the new summary stats
# ---------------------------------------------------------------------

def test_dashboard_shows_summary_stats(client):
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Overall Progress" in body
    assert "Labs Completed" in body
    assert "Total Score" in body
    assert "Total Hints Used" in body
    assert "Current Learning Mode" in body
    assert "Recommended Next Lab" in body


def test_dashboard_recommends_first_incomplete_lab(client):
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Lab 2" in body.split("Recommended Next Lab")[1][:200]


# ---------------------------------------------------------------------
# 10. Burp Suite guide page
# ---------------------------------------------------------------------

def test_burp_guide_loads(client):
    r = client.get("/burp-guide")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Burp Suite" in body
    assert "systems you own" in body


# ---------------------------------------------------------------------
# 11. Secure vs vulnerable code shown after completion
# ---------------------------------------------------------------------

def test_code_comparison_shown_after_completion(client):
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    assert "Vulnerable vs. Secure Code" in body
    assert "Vulnerable approach" in body
    assert "Secure approach" in body


# ---------------------------------------------------------------------
# 12. Health check endpoint
# ---------------------------------------------------------------------

def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data == {"status": "ok", "service": "cyberlab"}


# ---------------------------------------------------------------------
# 13. Open redirect protection (redirect_safety.safe_redirect_target +
#     enforcement on every route that accepts a "next" parameter)
# ---------------------------------------------------------------------

from redirect_safety import safe_redirect_target


@pytest.mark.parametrize("bad_next", [
    "https://evil.example",
    "http://evil.example",
    "//evil.example",
    "///evil.example",
    "https://evil.example/lab1/",
    "javascript:alert(1)",
    "/\\evil.example",
])
def test_safe_redirect_target_rejects_external_and_protocol_relative(bad_next):
    assert safe_redirect_target(bad_next, default="/") == "/"


@pytest.mark.parametrize("good_next", ["/", "/dashboard", "/lab1/", "/lab3/invoice/1"])
def test_safe_redirect_target_allows_internal_paths(good_next):
    assert safe_redirect_target(good_next, default="/fallback") == good_next


def test_safe_redirect_target_missing_uses_default():
    assert safe_redirect_target(None, default="/dashboard") == "/dashboard"
    assert safe_redirect_target("", default="/dashboard") == "/dashboard"


def test_submit_flag_route_rejects_external_next(client):
    r = client.post(
        "/submit-flag",
        data={"lab_id": "lab1", "flag": "wrong", "next": "https://evil.example/steal"},
    )
    assert r.status_code == 302
    assert r.headers["Location"] == "/"  # falls back to home, never the external URL


def test_hint_route_rejects_protocol_relative_next(client):
    r = client.post("/hint/lab1/1", data={"next": "//evil.example"})
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/")
    assert "evil.example" not in r.headers["Location"]


def test_reset_route_rejects_external_next(client):
    r = client.post("/reset/lab1", data={"next": "http://evil.example"})
    assert r.status_code == 302
    assert "evil.example" not in r.headers["Location"]


def test_mode_route_accepts_valid_internal_next(client):
    r = client.post("/mode", data={"mode": "beginner", "next": "/lab2/"})
    assert r.status_code == 302
    assert r.headers["Location"] == "/lab2/"


# ---------------------------------------------------------------------
# 14. Progress (completion) vs. score are independent
# ---------------------------------------------------------------------

def test_progress_reflects_completion_not_score(client):
    # Complete lab1 using 2 hints (score < 100), leave everything else
    # untouched. Progress should be 1/5 = 20%, regardless of score lost
    # to hints.
    client.post("/hint/lab1/1", data={"next": "/lab1/"})
    client.post("/hint/lab1/2", data={"next": "/lab1/"})
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "20%" in dash            # 1 of 5 labs completed
    assert "80/100" in dash         # score still reduced by hints
    assert "Labs Completed: <strong>1/5</strong>" in dash.replace("\n", "")


def test_full_completion_with_hints_still_shows_100_percent_progress(client):
    for lab_id, flag in FLAGS.items():
        client.post(f"/hint/{lab_id}/1", data={"next": f"/{lab_id}/"})
        client.post("/submit-flag", data={"lab_id": lab_id, "flag": flag, "next": f"/{lab_id}/"})
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "100%" in dash
    assert "Labs Completed: <strong>5/5</strong>" in dash.replace("\n", "")
    # Score is well below max (450/500) because every lab used a hint --
    # progress must not reflect that.
    assert "450/500" in dash


# ---------------------------------------------------------------------
# 15. Learning stage tracking is independent of hint usage
# ---------------------------------------------------------------------

def test_using_a_hint_does_not_mark_identified(client):
    client.post("/mode", data={"mode": "beginner", "next": "/lab1/"})
    client.post("/hint/lab1/1", data={"next": "/lab1/"})
    client.post("/hint/lab1/2", data={"next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    # Stage 3 should still show as pending -- hints alone never mark it.
    assert '<li class="pending">[ ] Identify the vulnerability</li>' in body


def test_explicit_identify_action_marks_stage(client):
    client.post("/mode", data={"mode": "beginner", "next": "/lab1/"})
    client.get("/lab1/")  # explore via visiting index counts as "started" only
    client.get("/lab1/backup/", headers={"Authorization": "Basic " + base64.b64encode(b"ops_readonly:B4ckup_View!").decode()})
    client.post("/stage/lab1/identify", data={"next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    assert '<li class="done">[✓] Identify the vulnerability</li>' in body


def test_remediation_stage_requires_explicit_view_after_completion(client):
    client.post("/mode", data={"mode": "beginner", "next": "/lab1/"})
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    body = client.get("/lab1/").get_data(as_text=True)
    assert '<li class="pending">[ ] Learn the remediation</li>' in body
    client.post("/stage/lab1/remediation", data={"next": "/lab1/"})
    body2 = client.get("/lab1/").get_data(as_text=True)
    assert '<li class="done">[✓] Learn the remediation</li>' in body2


def test_remediation_stage_ignored_before_completion(client):
    client.post("/mode", data={"mode": "beginner", "next": "/lab2/"})
    client.post("/stage/lab2/remediation", data={"next": "/lab2/"})
    body = client.get("/lab2/").get_data(as_text=True)
    # lab2 was never completed, so the remediation-viewed action must be
    # a no-op -- the stage stays pending.
    assert '<li class="pending">[ ] Learn the remediation</li>' in body


# ---------------------------------------------------------------------
# 16. Achievements
# ---------------------------------------------------------------------

def test_no_achievements_unlocked_initially(client):
    body = client.get("/dashboard").get_data(as_text=True)
    assert "✓ Unlocked" not in body


def test_first_steps_achievement_unlocks_after_one_lab(client):
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    body = client.get("/dashboard").get_data(as_text=True)
    assert "First Steps" in body
    section = body.split("First Steps")[1][:300]
    assert "✓ Unlocked" in section


def test_graduate_achievement_requires_all_five(client):
    for i, (lab_id, flag) in enumerate(FLAGS.items()):
        client.post("/submit-flag", data={"lab_id": lab_id, "flag": flag, "next": f"/{lab_id}/"})
        body = client.get("/dashboard").get_data(as_text=True)
        graduate_section = body.split("CyberLab Graduate")[1][:300]
        if i < 4:
            assert "✓ Unlocked" not in graduate_section
        else:
            assert "✓ Unlocked" in graduate_section


def test_perfect_score_requires_no_hints(client):
    for lab_id, flag in FLAGS.items():
        client.post(f"/hint/{lab_id}/1", data={"next": f"/{lab_id}/"})
        client.post("/submit-flag", data={"lab_id": lab_id, "flag": flag, "next": f"/{lab_id}/"})
    body = client.get("/dashboard").get_data(as_text=True)
    perfect_section = body.split("Perfect Score")[1][:300]
    assert "✓ Unlocked" not in perfect_section  # hints were used on every lab


# ---------------------------------------------------------------------
# 17. Secret key configuration
# ---------------------------------------------------------------------

def test_secret_key_is_not_the_old_hardcoded_literal(client):
    # Regression guard: the old, single hardcoded literal should never
    # come back as the *only* possible value.
    assert flask_app.secret_key != "lab-only-not-for-production-do-not-reuse"


def test_secret_key_is_configured(client):
    assert flask_app.secret_key  # non-empty, sourced from env or documented fallback


# ---------------------------------------------------------------------
# 18. Test isolation
# ---------------------------------------------------------------------

def test_sessions_are_isolated_between_tests_a(client):
    # Runs before test_sessions_are_isolated_between_tests_b alphabetically
    # is not guaranteed by pytest, but each gets a brand-new `client` --
    # this pair fails if state were ever shared globally instead of
    # per-session.
    client.post("/submit-flag", data={"lab_id": "lab1", "flag": FLAGS["lab1"], "next": "/lab1/"})
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "Labs Completed: <strong>1/5</strong>" in dash.replace("\n", "")


def test_sessions_are_isolated_between_tests_b(client):
    # A fresh `client` fixture means a fresh cookie jar means no session
    # at all yet -- if test isolation were broken, this would inherit
    # test_a's completed lab1.
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "Labs Completed: <strong>0/5</strong>" in dash.replace("\n", "")
