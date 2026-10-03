"""Regression tests for the v5 fixes: case-insensitive usernames, lockout that
strangers can't abuse, and no double-scoring of a replayed answer."""
import models
from app import app
from extensions import db
from services import lockout


def _login(c, name, pw):
    return c.post('/login', data={'username': name, 'password': pw})


def test_usernames_are_case_insensitive(client):
    assert client.post('/register', data={'username': 'Casey', 'password': 'password123'}).status_code == 302
    with app.test_client() as c2:
        r = c2.post('/register', data={'username': 'cAsEy', 'password': 'password123'})
        assert r.status_code == 200 and b'taken' in r.data.lower()
    with app.test_client() as c3:
        assert _login(c3, 'CASEY', 'password123').status_code == 302   # logs in with any casing


def test_stranger_cannot_lock_out_a_real_user(client):
    client.post('/register', data={'username': 'victim1', 'password': 'password123'})
    client.post('/logout')
    with app.app_context():
        # Five failures from the attacker's IP...
        for _ in range(5):
            lockout.record_failure('victim1', ip='6.6.6.6')
        assert lockout.is_locked('victim1', '6.6.6.6') is True
        # ...must not stop the real owner on a different IP.
        assert lockout.is_locked('victim1', '10.0.0.5') is False


def test_distributed_guessing_still_hits_global_limit(client, monkeypatch):
    monkeypatch.setenv('LOGIN_MAX_FAILURES_GLOBAL', '8')
    with app.app_context():
        for i in range(8):
            lockout.record_failure('target1', ip=f'7.7.7.{i}')
        assert lockout.is_locked('target1', '10.0.0.9') is True


def test_replayed_correct_answer_reports_zero_xp(auth_client):
    from tests.test_lab_engine import _add_lab, LAB, M1, Q1
    client, _ = auth_client
    with app.app_context():
        _add_lab(LAB, 1)
        db.session.commit()
    sid = client.post('/api/lab-engine/start', json={'lab_id': LAB}).get_json()['session_id']
    body = {'session_id': sid, 'mission_id': M1, 'question_id': Q1, 'answer': 'sqli'}
    first = client.post('/api/lab-engine/submit-answer', json=body).get_json()
    again = client.post('/api/lab-engine/submit-answer', json=body).get_json()
    assert first['xp'] == 50 and again['xp'] == 0
