"""
Lab 2 — Login Bypass (Classic SQL Injection)

v3: significantly harder than v2.
  - No footer hint revealing the admin username anymore. Instead, a
    separate "forgot password" feature leaks account existence through
    a differing response message -- a second, realistic bug
    (username/account enumeration) that has to be exploited first to
    even know what to target.
  - The login endpoint now filters out the literal sequence "--"
    (case-insensitive), which is the "fix" a beginner often reaches
    for first. It doesn't actually stop injection -- SQLite also
    treats an UNCLOSED "/* " as "ignore everything after this," so
    that becomes the way through.
"""
import re
import sqlite3
from flask import Blueprint, render_template, request

import progress

lab2_bp = Blueprint("lab2", __name__, template_folder="../templates/lab2")

FLAG = "CYBERLAB{quotes_in_user_input_are_never_just_quotes}"

VALID_USERNAMES = {"sumit", "ayush", "tejas", "sahil", "sayali", "root_ops"}


def get_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)")
    conn.execute("INSERT INTO users (username, password, role) VALUES ('sumit', 'H0rse!Battery', 'user')")
    conn.execute("INSERT INTO users (username, password, role) VALUES ('ayush', 'correct-horse-42', 'user')")
    conn.execute("INSERT INTO users (username, password, role) VALUES ('tejas', 'pixel-forge-9', 'user')")
    conn.execute("INSERT INTO users (username, password, role) VALUES ('sahil', 'quietriver77', 'user')")
    conn.execute("INSERT INTO users (username, password, role) VALUES ('sayali', 'gridlock-echo', 'user')")
    conn.execute("INSERT INTO users (username, password, role) VALUES ('root_ops', 'x9#Qz7!mK2vL', 'admin')")
    conn.commit()
    return conn


def strip_double_dash(s: str) -> str:
    # VULNERABLE "FIX" ON PURPOSE: blocks the obvious comment sequence,
    # nothing else. A determined attacker just uses a different comment
    # style that SQLite also honors.
    return re.sub(r"--", "", s, flags=re.IGNORECASE)


@lab2_bp.route("/")
def index():
    ctx = progress.lab_context("lab2")
    return render_template("lab2/index.html", **ctx)


@lab2_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    progress.mark_explored("lab2")
    message = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username in VALID_USERNAMES:
            message = f"If {username} has a verified email on file, reset instructions were sent."
        else:
            message = "We couldn't find an account with that username."
    return render_template("lab2/forgot_password.html", message=message)


@lab2_bp.route("/login", methods=["GET", "POST"])
def login():
    progress.mark_explored("lab2")
    error = None
    user_row = None

    if request.method == "POST":
        username = strip_double_dash(request.form.get("username", ""))
        password = strip_double_dash(request.form.get("password", ""))

        # VULNERABLE ON PURPOSE: raw string interpolation into SQL.
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"

        conn = get_db()
        try:
            cur = conn.execute(query)
            user_row = cur.fetchone()
        except sqlite3.OperationalError:
            error = "Something went wrong processing your request. Please try again."
        finally:
            conn.close()

        if user_row is None and error is None:
            error = "Invalid username or password."

    return render_template(
        "lab2/login.html",
        error=error,
        user=dict(user_row) if user_row else None,
        flag=FLAG,
    )
