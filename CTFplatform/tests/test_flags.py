import models
from extensions import db
from services.security import safe_equals


def _add(*objs):
    db.session.add_all(objs)
    db.session.commit()


def test_safe_equals():
    assert safe_equals('FLAG{a}', 'FLAG{a}')
    assert not safe_equals('FLAG{a}', 'FLAG{b}')
    assert not safe_equals('FLAG{a}', 'FLAG{a} ')
    # odd JSON types must not raise
    assert not safe_equals(123, 'FLAG{a}')
    assert not safe_equals(None, 'x')
    assert not safe_equals(['x'], 'x')
    assert safe_equals('flág', 'flág')  # non-ascii is fine


def test_flag_requires_login(client):
    r = client.post('/api/flag', json={'lab_id': 'lab1', 'flag': 'x'})
    assert r.status_code == 401


def test_lab_flag_correct_and_incorrect(auth_client):
    client, _ = auth_client
    from app import app
    with app.app_context():
        _add(models.Flag(id='f1', lab_id='lab1', flag_value='FLAG{secret}'))
    bad = client.post('/api/flag', json={'lab_id': 'lab1', 'flag': 'FLAG{nope}'})
    assert bad.json['success'] is False
    good = client.post('/api/flag', json={'lab_id': 'lab1', 'flag': 'FLAG{secret}'})
    assert good.json['success'] is True


def test_flag_with_non_string_value_does_not_crash(auth_client):
    client, _ = auth_client
    from app import app
    with app.app_context():
        _add(models.Flag(id='f2', lab_id='lab1', flag_value='FLAG{secret}'))
    for weird in (123, None, ['FLAG{secret}'], {'a': 1}):
        r = client.post('/api/flag', json={'lab_id': 'lab1', 'flag': weird})
        assert r.status_code == 200
        assert r.json['success'] is False


def test_unknown_lab_flag_is_rejected(auth_client):
    client, _ = auth_client
    r = client.post('/api/flag', json={'lab_id': 'does-not-exist', 'flag': 'x'})
    assert r.json['success'] is False


def test_missing_fields_rejected(auth_client):
    client, _ = auth_client
    assert client.post('/api/flag', json={'lab_id': 'lab1'}).status_code == 400
    assert client.post('/api/flag', json={}).status_code == 400


def test_manual_lab_flag(auth_client):
    client, user_id = auth_client
    from app import app
    with app.app_context():
        _add(models.ManualLab(id='mlabx', name='n', topic='t', difficulty='d', target_type='vm'),
             models.ManualLabFlag(manual_lab_id='mlabx', flag_value='TECHCORP{ok}'))
    assert client.post('/api/manual-lab/flag', json={'lab_id': 'mlabx', 'flag': 'bad'}).json['success'] is False
    assert client.post('/api/manual-lab/flag', json={'lab_id': 'mlabx', 'flag': 'TECHCORP{ok}'}).json['success'] is True


def test_challenge_flag(auth_client):
    client, _ = auth_client
    from app import app
    with app.app_context():
        _add(models.Challenge(id='c1', name='c', category='web', description='d', flag_value='CTF{c1}'))
    assert client.post('/api/challenges/submit', json={'challenge_id': 'c1', 'flag': 'nope'}).json['success'] is False
    assert client.post('/api/challenges/submit', json={'challenge_id': 'c1', 'flag': 'CTF{c1}'}).json['success'] is True
    assert client.post('/api/challenges/submit', json={'challenge_id': 'zzz', 'flag': 'x'}).status_code == 404
