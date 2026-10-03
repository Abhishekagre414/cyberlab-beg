"""Test fixtures.

Every test run gets its OWN throw-away SQLite file. The environment must be
configured BEFORE `app` is imported, because config.py reads DATABASE_URL at
import time. (The old fixture pointed at a temp file after import, so tests
silently ran against - and wrote into - the real database/hacktheai.db.)
"""
import os
import tempfile

import pytest

_fd, _DB_PATH = tempfile.mkstemp(suffix='.db')
os.close(_fd)
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_PATH}'
os.environ['DATABASE_PATH'] = _DB_PATH          # used by raw-sqlite assertions in tests
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['AUTO_INIT_DB'] = 'false'
os.environ.pop('REDIS_URL', None)

from app import app, limiter  # noqa: E402
from extensions import db      # noqa: E402
import models                  # noqa: E402
from services.progress_service import initialize_user_progress  # noqa: E402


def _seed():
    db.session.add_all([
        models.Lab(id='lab1', name='L1', topic='T1', difficulty='B'),
        models.Lab(id='lab2', name='L2', topic='T2', difficulty='B'),
        models.Lab(id='lab4', name='L4', topic='T4', difficulty='B'),
        models.Mission(id='lab1_m1', lab_id='lab1', mission_number=1, title='M1', description='D1'),
        models.Mission(id='lab2_m1', lab_id='lab2', mission_number=1, title='M1', description='D1'),
        models.Mission(id='lab4_m1', lab_id='lab4', mission_number=1, title='M1', description='D1'),
        models.MissionQuiz(id='q1', mission_id='lab4_m1', question='Q', answer='browser',
                           explanation='E', xp_reward=150),
        models.Hint(id='h1', mission_id='lab1_m1', hint_text='Network tab', xp_cost=10, sort_order=1),
        models.Hint(id='h2', mission_id='lab1_m1', hint_text='X-Custom-Flag', xp_cost=20, sort_order=2),
        models.Evidence(id='ev1', lab_id='lab1', name='Evidence 1', description='d'),
    ])
    db.session.commit()


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False

    with app.app_context():
        db.drop_all()
        db.create_all()
        _seed()

    with app.test_client() as c:
        yield c

    with app.app_context():
        db.session.remove()


@pytest.fixture
def auth_client(client):
    """Registers and logs in a test user, returning the client and user_id."""
    response = client.post('/register', data={
        'username': 'testuser',
        'password': 'testpassword1',
    })
    assert response.status_code == 302, f"Registration failed: {response.data.decode('utf-8')[:500]}"

    with client.session_transaction() as sess:
        user_id = sess['user_id']
    return client, user_id


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass
