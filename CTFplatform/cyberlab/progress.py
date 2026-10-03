"""
Simple, transparent, session-based progress tracking. No database --
this is a local single-user training tool, so Flask's signed session
cookie is enough state, and it naturally resets if you clear cookies
or use a fresh browser profile.

Scoring: each lab is worth 100 points. Each hint used costs 10 points,
capped so a fully-hinted solve is still worth something (10 minimum).
"""
from flask import session
from labs.lab_meta import LAB_IDS, HINTS, STAGE_LABELS, DEFAULT_MODE, MODES, ACHIEVEMENTS, lab_nav, LEARNING_ORDER, LAB_TITLES, DIFFICULTY

MAX_SCORE = 100
HINT_PENALTY = 10
MIN_SCORE = 10


def _blank_lab_progress():
    return {
        "status": "not_started",
        "score": 0,
        "hints_used": 0,
        "completed": False,
        # Stage tracking is intentionally independent of score/hints --
        # see mark_explored/mark_identified/mark_remediation_viewed below.
        # Using a hint is NOT, by itself, treated as "identifying" the bug.
        "explored": False,
        "identified": False,
        "remediation_viewed": False,
    }


def _ensure():
    if "progress" not in session or not isinstance(session.get("progress"), dict):
        session["progress"] = {lab: _blank_lab_progress() for lab in LAB_IDS}
        session.modified = True
    else:
        # Backfill any new fields for sessions created before this field
        # existed, without wiping existing progress.
        changed = False
        for lab in LAB_IDS:
            entry = session["progress"].setdefault(lab, _blank_lab_progress())
            for key, default in _blank_lab_progress().items():
                if key not in entry:
                    entry[key] = default
                    changed = True
        if changed:
            session.modified = True


# ---------------------------------------------------------------------
# Learning mode (beginner / normal / challenge)
# ---------------------------------------------------------------------

def get_mode():
    return session.get("mode", DEFAULT_MODE)


def set_mode(mode):
    if mode in MODES:
        session["mode"] = mode
        session.modified = True
    return get_mode()


def mark_explored(lab_id):
    """Call this from any secondary route within a lab (not the index
    page) so the 'Explore the application' stage can be marked done.
    This reflects genuine interaction with the vulnerable app -- not a
    hint or a guess."""
    _ensure()
    p = session["progress"]
    if lab_id in p and not p[lab_id].get("explored"):
        p[lab_id]["explored"] = True
        session["progress"] = p
        session.modified = True


def mark_identified(lab_id):
    """Marks the 'Identify the vulnerability' stage. Deliberately NOT
    triggered by hint usage -- a hint tells you where to look, it
    doesn't confirm you understood what you found. This is set by an
    explicit student action (a self-report confirmation, or -- where a
    lab has one -- a concrete discovery signal like tripping a filter
    or triggering a real error)."""
    _ensure()
    p = session["progress"]
    if lab_id in p and not p[lab_id].get("identified"):
        p[lab_id]["identified"] = True
        session["progress"] = p
        session.modified = True


def mark_remediation_viewed(lab_id):
    """Marks 'Learn the remediation'. Only meaningful once the lab is
    completed (the writeup only exists at that point), and only set
    when the student actually opens/views it -- not merely because they
    finished the lab."""
    _ensure()
    p = session["progress"]
    if lab_id in p and p[lab_id].get("completed") and not p[lab_id].get("remediation_viewed"):
        p[lab_id]["remediation_viewed"] = True
        session["progress"] = p
        session.modified = True


def get_progress():
    _ensure()
    return session["progress"]


def mark_started(lab_id):
    _ensure()
    p = session["progress"]
    if lab_id in p and p[lab_id]["status"] == "not_started":
        p[lab_id]["status"] = "in_progress"
        session["progress"] = p
        session.modified = True


def use_hint(lab_id):
    """Unlock the next hint level for this lab, if any remain."""
    _ensure()
    p = session["progress"]
    if lab_id not in p or p[lab_id]["completed"]:
        return p.get(lab_id, {}).get("hints_used", 0)
    max_levels = len(HINTS.get(lab_id, []))
    if p[lab_id]["hints_used"] < max_levels:
        p[lab_id]["hints_used"] += 1
        p[lab_id]["status"] = "in_progress"
        session["progress"] = p
        session.modified = True
    return p[lab_id]["hints_used"]


def submit_flag(lab_id, submitted, correct_flag):
    """Returns True if the flag was correct. Idempotent -- resubmitting
    a correct flag doesn't re-score or double-count."""
    _ensure()
    p = session["progress"]
    if lab_id not in p:
        return False
    submitted = (submitted or "").strip()
    if submitted == correct_flag:
        if not p[lab_id]["completed"]:
            score = max(MAX_SCORE - p[lab_id]["hints_used"] * HINT_PENALTY, MIN_SCORE)
            p[lab_id]["score"] = score
            p[lab_id]["completed"] = True
            p[lab_id]["status"] = "completed"
            session["progress"] = p
            session.modified = True
        return True
    return False


def reset_lab(lab_id):
    _ensure()
    p = session["progress"]
    if lab_id in p:
        p[lab_id] = _blank_lab_progress()
        session["progress"] = p
        session.modified = True


# ---------------------------------------------------------------------
# Progress (completion) vs. score -- kept deliberately independent.
# Progress answers "how far through the course is the student", and is
# NEVER reduced by hint usage. Score is a separate, optional signal of
# how cleanly each lab was solved.
# ---------------------------------------------------------------------

def overall_percentage():
    """Course completion percentage: completed_labs / total_labs * 100.
    Intentionally has nothing to do with score or hints used."""
    p = get_progress()
    if not LAB_IDS:
        return 0
    completed = sum(1 for x in p.values() if x.get("completed"))
    return round(completed / len(LAB_IDS) * 100)


def labs_completed_count():
    return sum(1 for x in get_progress().values() if x.get("completed"))


def total_score():
    return sum(x.get("score", 0) for x in get_progress().values())


def max_possible_score():
    return MAX_SCORE * len(LAB_IDS)


def total_hints_used():
    return sum(x.get("hints_used", 0) for x in get_progress().values())


def get_achievements():
    """Compute which achievements are unlocked right now, purely from
    session progress -- no separate achievement state to keep in sync."""
    p = get_progress()
    completed = labs_completed_count()
    perfect = completed == len(LAB_IDS) and all(
        x.get("score", 0) == MAX_SCORE for x in p.values()
    )
    unlocked = []
    for ach in ACHIEVEMENTS:
        if ach["id"] == "perfect_score":
            earned = perfect
        else:
            earned = completed >= ach["threshold"]
        unlocked.append({**ach, "earned": earned})
    return unlocked


def get_stages(lab_id):
    """Compute the 5 step-by-step learning stages for a lab. Each stage
    is backed by its own independent signal -- notably, 'Identify the
    vulnerability' and 'Learn the remediation' are NOT inferred from
    hint usage or mere completion; they require their own explicit
    action (see mark_identified / mark_remediation_viewed)."""
    p = get_progress().get(lab_id, {})
    started = p.get("status", "not_started") != "not_started"
    explored = p.get("explored", False)
    identified = p.get("identified", False)
    completed = p.get("completed", False)
    remediation_viewed = p.get("remediation_viewed", False)
    done_flags = [started, explored, identified, completed, remediation_viewed]
    return [
        {"label": label, "done": done}
        for label, done in zip(STAGE_LABELS, done_flags)
    ]


def lab_context(lab_id):
    """Bundle of everything a lab's index template needs to render the
    hints/reset/progress/stage-tracker/nav/completion widgets."""
    mark_started(lab_id)
    p = get_progress()[lab_id]
    all_hints = HINTS.get(lab_id, [])
    unlocked_hints = all_hints[: p["hints_used"]]
    prev_lab, next_lab = lab_nav(lab_id)

    # For the post-completion screen: the next lab in the recommended
    # order that isn't finished yet (falls back to the plain "next" lab
    # if everything ahead of it is already done, or None if this was
    # the last remaining lab).
    prog_all = get_progress()
    next_incomplete = None
    if lab_id in LEARNING_ORDER:
        idx = LEARNING_ORDER.index(lab_id)
        for lid in LEARNING_ORDER[idx + 1:]:
            if not prog_all.get(lid, {}).get("completed"):
                next_incomplete = {"id": lid, "title": LAB_TITLES[lid], "difficulty": DIFFICULTY[lid], "url": f"/{lid}/"}
                break

    return {
        "lab_id": lab_id,
        "prog": p,
        "unlocked_hints": unlocked_hints,
        "total_hint_levels": len(all_hints),
        "stages": get_stages(lab_id),
        "mode": get_mode(),
        "prev_lab": prev_lab,
        "next_lab": next_lab,
        "next_recommended_lab": next_incomplete,
    }
