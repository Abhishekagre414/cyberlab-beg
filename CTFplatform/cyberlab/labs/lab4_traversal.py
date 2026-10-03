"""
Lab 4 — Escape the Downloads Folder (Path Traversal)

v2: harder than the first pass. There's now a filter that blocks the
literal "../" sequence -- so naive traversal attempts get stripped and
silently do nothing. This mirrors a very common REAL mistake: a
single, non-recursive string.replace("../", "") that can be defeated
by a classic bypass string like "....//" which, after ONE pass of that
replace, collapses back down into "../" -- because the replace call
only runs once, not in a loop until no more matches exist.

Safety note: sandboxed to `server_files/` inside this project, same as
before. The vulnerable filter only tries to block ".." -- it doesn't
know or care about the project sandbox boundary at all.
"""
import os
from flask import Blueprint, render_template, request, abort

import progress

lab4_bp = Blueprint("lab4", __name__, template_folder="../templates/lab4")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_files"))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
FLAG = "CYBERLAB{dot_dot_slash_still_works_if_nobody_checks}"


def naive_sanitize(filename: str) -> str:
    # VULNERABLE ON PURPOSE: single, non-recursive replace. Looks like a
    # fix, isn't one -- a classic beginner security mistake.
    return filename.replace("../", "")


@lab4_bp.route("/")
def index():
    files = sorted(os.listdir(DOWNLOADS_DIR))
    ctx = progress.lab_context("lab4")
    return render_template("lab4/index.html", files=files, **ctx)


@lab4_bp.route("/download")
def download():
    progress.mark_explored("lab4")
    filename = request.args.get("file", "")
    if not filename:
        abort(400)

    cleaned = naive_sanitize(filename)
    requested_path = os.path.join(DOWNLOADS_DIR, cleaned)
    resolved_path = os.path.abspath(requested_path)

    # SANDBOX SAFETY NET -- not part of the "real app" logic being taught,
    # just here so this lab can never read anything outside the project
    # folder no matter what you throw at it.
    if not resolved_path.startswith(BASE_DIR):
        return render_template(
            "lab4/download.html",
            filename=filename,
            blocked=True,
            content=None,
            escaped=False,
            found_flag=False,
            flag=None,
        )

    if not os.path.isfile(resolved_path):
        abort(404)

    with open(resolved_path, "r", errors="replace") as f:
        content = f.read()

    escaped = not resolved_path.startswith(DOWNLOADS_DIR + os.sep)
    found_flag = FLAG in content

    return render_template(
        "lab4/download.html",
        filename=filename,
        blocked=False,
        content=content,
        escaped=escaped,
        found_flag=found_flag,
        flag=FLAG,
    )
