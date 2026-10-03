import models
from extensions import db


def _register(client, username='newuser', password='goodpass123', email=''):
    return client.post('/register', data={'username': username, 'password': password, 'email': email})


def test_weak_passwords_rejected(client):
    assert b'at least 8' in _register(client, password='short1').data
    assert b'letter and one number' in _register(client, password='onlyletters').data
    assert b'letter and one number' in _register(client, password='12345678').data
    assert b'same as your username' in _register(client, username='sameuser1', password='sameuser1').data


def test_bad_username_and_email_rejected(client):
    assert b'Username must be' in _register(client, username='a b').data
    assert b'Username must be' in _register(client, username='ab').data
    assert b'valid email' in _register(client, email='not-an-email').data


def test_register_ok_and_duplicate(client):
    assert _register(client).status_code == 302
    client.post('/logout')
    assert b'Username taken' in _register(client).data


def test_two_users_without_email_do_not_collide(client):
    # '' used to be stored as an empty string and trip the UNIQUE(email) index.
    assert _register(client, username='first1').status_code == 302
    client.post('/logout')
    assert _register(client, username='second1').status_code == 302


def test_login_discards_preexisting_session_data(client):
    _register(client, username='fixate1')
    client.post('/logout')
    with client.session_transaction() as sess:
        sess['planted'] = 'attacker-value'
    r = client.post('/login', data={'username': 'fixate1', 'password': 'goodpass123'})
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert 'planted' not in sess
        assert 'user_id' in sess


def test_logout_clears_whole_session(client):
    _register(client, username='bye1')
    with client.session_transaction() as sess:
        sess['extra'] = 1
    client.post('/logout')
    with client.session_transaction() as sess:
        assert dict(sess) == {}


def test_login_error_is_identical_for_unknown_and_wrong_password(client):
    _register(client, username='real1')
    client.post('/logout')
    a = client.post('/login', data={'username': 'real1', 'password': 'wrongpass1'})
    b = client.post('/login', data={'username': 'ghost1', 'password': 'wrongpass1'})
    assert a.status_code == b.status_code == 200
    assert b'Invalid username or password' in a.data
    assert b'Invalid username or password' in b.data


def test_password_hash_fits_column():
    # scrypt hashes are ~162 chars; the column used to be VARCHAR(128).
    from werkzeug.security import generate_password_hash
    assert len(generate_password_hash('x')) <= models.User.password.type.length


def test_logout_requires_post(client):
    _register(client, username='getlogout1')
    assert client.get('/logout').status_code == 405
    with client.session_transaction() as sess:
        assert 'user_id' in sess  # a GET (e.g. a hostile <img src>) must not log the user out


def test_lockout_after_repeated_failures(client):
    _register(client, username='lockme1', password='goodpass123')
    client.post('/logout')
    for _ in range(5):
        r = client.post('/login', data={'username': 'lockme1', 'password': 'wrongpass1'})
        assert r.status_code == 200 and b'Invalid username or password' in r.data
    # Locked now - even the CORRECT password is refused until the window passes.
    r = client.post('/login', data={'username': 'lockme1', 'password': 'goodpass123'})
    assert r.status_code == 429 and b'Too many failed attempts' in r.data
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_lockout_is_identical_for_unknown_usernames(client):
    for _ in range(5):
        client.post('/login', data={'username': 'ghost-user', 'password': 'whatever1'})
    r = client.post('/login', data={'username': 'ghost-user', 'password': 'whatever1'})
    assert r.status_code == 429          # same behaviour as a real account: no user enumeration


def test_lockout_expires(client, monkeypatch):
    from datetime import datetime, timedelta
    from services import lockout
    _register(client, username='lockme2', password='goodpass123')
    client.post('/logout')
    for _ in range(5):
        client.post('/login', data={'username': 'lockme2', 'password': 'wrongpass1'})
    assert client.post('/login', data={'username': 'lockme2', 'password': 'goodpass123'}).status_code == 429
    later = datetime.utcnow() + timedelta(minutes=16)
    monkeypatch.setattr(lockout, 'datetime', type('D', (), {'utcnow': staticmethod(lambda: later)}))
    assert client.post('/login', data={'username': 'lockme2', 'password': 'goodpass123'}).status_code == 302
