from flask import Blueprint, render_template, request, redirect, url_for, session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from services.progress_service import initialize_user_progress
from services.audit_service import log_action
from services.user_service import get_user_by_username, create_user
from services.security import (DUMMY_PASSWORD_HASH, validate_password,
                               validate_username, validate_email)
from services import lockout
from extensions import limiter, db

auth_bp = Blueprint('auth', __name__)


def is_valid_password(password, username=""):
    return validate_password(password, username)


def _start_session(user_id, username):
    """Begin a fresh authenticated session.

    Clearing first discards anything an attacker may have planted in a
    pre-login session (session fixation) and any stale keys.
    """
    session.clear()
    session['user_id'] = user_id
    session['username'] = username
    session.permanent = True  # honours PERMANENT_SESSION_LIFETIME


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = get_user_by_username(username)
        # Always run one hash check so unknown users cost the same time as
        # known ones (prevents username enumeration through timing).
        stored_hash = user.password if user else DUMMY_PASSWORD_HASH
        password_ok = check_password_hash(stored_hash, password)
        # Checked after the hash so a locked and an unlocked account cost the
        # same time; keyed by submitted name so unknown users lock identically.
        if lockout.is_locked(username, request.remote_addr):
            return render_template(
                'login.html',
                error=f"Too many failed attempts. Try again in {lockout.lock_minutes()} minutes."), 429
        if user and password_ok:
            _start_session(user.id, user.username)
            log_action(user.id, 'LOGIN_SUCCESS')
            return redirect(url_for('dashboard.dashboard'))
        lockout.record_failure(username, user.id if user else None, request.remote_addr)
        return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        email = (request.form.get('email') or '').strip() or None

        for ok, msg in (validate_username(username),
                        validate_password(password, username),
                        validate_email(email)):
            if not ok:
                return render_template('register.html', error=msg)

        if get_user_by_username(username):
            return render_template('register.html', error="Username taken.")

        try:
            hashed_password = generate_password_hash(password)
            user_id = create_user(username, hashed_password, email)
            # Initialize progress using the centralized service
            initialize_user_progress(user_id)

            db.session.commit()
            _start_session(user_id, username)
            log_action(user_id, 'REGISTER')
            return redirect(url_for('dashboard.dashboard'))
        except IntegrityError:
            db.session.rollback()
            return render_template('register.html', error="Username taken.")
    return render_template('register.html')


@auth_bp.route('/logout', methods=['POST'])
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], 'LOGOUT')
    session.clear()
    return redirect(url_for('index'))
