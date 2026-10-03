"""Failed-login lockout, backed by the audit log (no schema change needed).

Two independent limits, both counted over a sliding window:

* per (username, client IP): LOGIN_MAX_FAILURES (default 5). Stops one
  attacker guessing a password, and - because the IP is part of the key -
  a stranger can NOT lock a real user out by failing logins from elsewhere.
* per username across all IPs: LOGIN_MAX_FAILURES_GLOBAL (default 30). A
  backstop against a distributed guessing attack; high enough that casual
  abuse can't use it to lock out an account.

Failures are keyed by the *submitted username* (case-insensitive) whether or
not the account exists, so lockouts don't reveal which accounts are real.
Timestamps are written in UTC so the comparison works on SQLite and Postgres.
"""
import os
from datetime import datetime, timedelta

from extensions import db
from models import AuditLog

ACTION = 'LOGIN_FAILED'


def _max_failures():
    return int(os.environ.get('LOGIN_MAX_FAILURES', 5))


def _max_failures_global():
    return int(os.environ.get('LOGIN_MAX_FAILURES_GLOBAL', 30))


def _window():
    return timedelta(minutes=int(os.environ.get('LOGIN_LOCK_MINUTES', 15)))


def _name(username):
    return (username or '').strip().lower()[:80]


def _user_key(username):
    return 'u:' + _name(username)


def _ip_key(username, ip):
    return f'u:{_name(username)}|ip:{(ip or "?")[:45]}'


def record_failure(username, user_id=None, ip=None):
    now = datetime.utcnow()
    # Two rows per failure: one per-IP key, one per-username key.
    db.session.add(AuditLog(user_id=user_id, action=ACTION, details=_ip_key(username, ip), timestamp=now))
    db.session.add(AuditLog(user_id=user_id, action=ACTION, details=_user_key(username), timestamp=now))
    db.session.commit()


def _count(key, since):
    return AuditLog.query.filter(
        AuditLog.action == ACTION,
        AuditLog.details == key,
        AuditLog.timestamp >= since,
    ).count()


def is_locked(username, ip=None):
    since = datetime.utcnow() - _window()
    if _count(_ip_key(username, ip), since) >= _max_failures():
        return True
    return _count(_user_key(username), since) >= _max_failures_global()


def lock_minutes():
    return int(_window().total_seconds() // 60)
