"""Tests for /api/lab-engine/* : session start, progress, answers, flags, hints, stop.

Labs here have no docker_config, so no container is ever launched.
"""
import pytest

import models
from app import app
from extensions import db

LAB = 'ulab-t1'
M1, M2 = f'{LAB}_m1', f'{LAB}_m2'
Q1, Q2 = f'{M1}_q1', f'{M2}_q1'
FLAG = 'FLAG{engine_test}'


def _add_lab(lab_id, sort_order, status='published', with_content=True):
    db.session.add(models.UploadedLab(
        id=lab_id, title=f'Lab {lab_id}', category='Web', difficulty='Beginner',
        total_points=300, status=status, sort_order=sort_order, docker_config='{}'))
    if not with_content:
        return
    db.session.add_all([
        models.UploadedLabMission(id=f'{lab_id}_m1', lab_id=lab_id, mission_number=1, title='M1', points=100),
        models.UploadedLabMission(id=f'{lab_id}_m2', lab_id=lab_id, mission_number=2, title='M2', points=100),
    ])
    db.session.flush()
    db.session.add_all([
        models.UploadedLabQuestion(id=f'{lab_id}_m1_q1', mission_id=f'{lab_id}_m1', question_text='Q1?',
                                   expected_answer='sqli', xp_reward=50, sort_order=1),
        models.UploadedLabQuestion(id=f'{lab_id}_m2_q1', mission_id=f'{lab_id}_m2', question_text='Q2?',
                                   expected_answer='xss', xp_reward=70, sort_order=1),
        models.UploadedLabHint(id=f'{lab_id}_m1_h1', mission_id=f'{lab_id}_m1', hint_text='first hint',
                               xp_cost=5, sort_order=1),
        models.UploadedLabHint(id=f'{lab_id}_m1_h2', mission_id=f'{lab_id}_m1', hint_text='second hint',
                               xp_cost=10, sort_order=2),
        models.UploadedLabFlag(id=f'{lab_id}_f1', lab_id=lab_id, flag_value=FLAG, points=100),
    ])


@pytest.fixture
def engine(auth_client):
    client, user_id = auth_client
    with app.app_context():
        _add_lab(LAB, 1)
        db.session.commit()
    return client


def _start(client, lab_id=LAB):
    return client.post('/api/lab-engine/start', json={'lab_id': lab_id})


def _sid(client):
    return _start(client).get_json()['session_id']


def _progress(client, sid):
    return client.post('/api/lab-engine/progress', json={'session_id': sid}).get_json()


def _answer(client, sid, mission, question, answer):
    return client.post('/api/lab-engine/submit-answer', json={
        'session_id': sid, 'mission_id': mission, 'question_id': question, 'answer': answer})


@pytest.fixture
def other_client():
    """A second, separately logged-in learner."""
    # No `with` block: two preserved request contexts open at once make Flask
    # pop them out of order ("Popped wrong app context") at teardown.
    c = app.test_client()
    assert c.post('/register', data={'username': 'intruder1', 'password': 'intruderpass1'}).status_code == 302
    yield c


# ---------------------------------------------------------------------- start
def test_all_endpoints_require_login(client):
    for path in ('start', 'progress', 'submit-answer', 'submit-flag', 'hint', 'stop'):
        assert client.post(f'/api/lab-engine/{path}', json={}).status_code == 401, path


def test_start_rejects_bad_input_and_unpublished_labs(engine):
    assert engine.post('/api/lab-engine/start', json={}).status_code == 400
    assert _start(engine, 'does-not-exist').status_code == 404
    with app.app_context():
        _add_lab('ulab-draft', 5, status='draft', with_content=False)
        db.session.commit()
    assert _start(engine, 'ulab-draft').status_code == 404


def test_start_creates_session_with_first_mission_open(engine):
    r = _start(engine)
    body = r.get_json()
    assert r.status_code == 200 and body['success'] and body['session_id'].startswith('sess-')
    assert body['target_url'] is None            # no docker_config -> no container
    prog = _progress(engine, body['session_id'])
    status = {m['mission_id']: m['status'] for m in prog['missions']}
    assert status == {M1: 'AVAILABLE', M2: 'LOCKED'}
    assert prog['score'] == 0 and prog['missions_total'] == 2


def test_start_again_resumes_same_session(engine):
    first = _sid(engine)
    assert _sid(engine) == first
    with app.app_context():
        assert models.LabSession.query.count() == 1


def test_learning_path_gate(engine):
    with app.app_context():
        _add_lab('ulab-t2', 2)
        db.session.commit()
    assert _start(engine, 'ulab-t2').status_code == 403      # earlier lab not started yet
    assert _start(engine, LAB).status_code == 200
    assert _start(engine, 'ulab-t2').status_code == 200      # now unlocked


# ------------------------------------------------------------------- progress
def test_progress_does_not_leak_answers_or_flags(engine):
    sid = _sid(engine)
    raw = engine.post('/api/lab-engine/progress', json={'session_id': sid}).data
    assert b'sqli' not in raw and b'xss' not in raw and FLAG.encode() not in raw


def test_other_users_cannot_touch_my_session(engine, other_client):
    sid = _sid(engine)
    attempts = {
        'progress': {'session_id': sid},
        'stop': {'session_id': sid},
        'hint': {'session_id': sid, 'mission_id': M1},
        'submit-flag': {'session_id': sid, 'flag': FLAG},
        'submit-answer': {'session_id': sid, 'mission_id': M1, 'question_id': Q1, 'answer': 'sqli'},
    }
    for path, payload in attempts.items():
        assert other_client.post(f'/api/lab-engine/{path}', json=payload).status_code == 404, path
    assert _progress(engine, sid)['score'] == 0
    assert _progress(engine, sid)['status'] == 'ACTIVE'


# -------------------------------------------------------------------- answers
def test_wrong_answer_scores_nothing(engine):
    sid = _sid(engine)
    body = _answer(engine, sid, M1, Q1, 'nope').get_json()
    assert body['success'] and body['correct'] is False and body['xp'] == 0
    assert _progress(engine, sid)['score'] == 0


def test_correct_answer_scores_once_and_unlocks_next_mission(engine):
    sid = _sid(engine)
    body = _answer(engine, sid, M1, Q1, 'SQLI').get_json()     # case-insensitive by default
    assert body['correct'] is True and body['xp'] == 50
    prog = _progress(engine, sid)
    assert prog['score'] == 50 and prog['missions_completed'] == 1
    assert {m['mission_id']: m['status'] for m in prog['missions']} == {M1: 'COMPLETED', M2: 'AVAILABLE'}
    _answer(engine, sid, M1, Q1, 'sqli')                      # replaying must not farm points
    assert _progress(engine, sid)['score'] == 50


def test_cannot_answer_a_locked_mission(engine):
    sid = _sid(engine)
    r = _answer(engine, sid, M2, Q2, 'xss')
    assert r.status_code == 403
    assert _progress(engine, sid)['score'] == 0


def test_answer_input_validation(engine):
    sid = _sid(engine)
    assert engine.post('/api/lab-engine/submit-answer', json={'session_id': sid}).status_code == 400
    assert _answer(engine, sid, M1, 'no-such-question', 'x').status_code == 404
    assert _answer(engine, sid, M2, Q1, 'sqli').status_code == 404   # question belongs to another mission
    assert _answer(engine, 'sess-unknown', M1, Q1, 'sqli').status_code == 404


# ---------------------------------------------------------------------- flags
def test_wrong_flag_is_rejected_and_lab_stays_active(engine):
    sid = _sid(engine)
    body = engine.post('/api/lab-engine/submit-flag', json={'session_id': sid, 'flag': 'FLAG{wrong}'}).get_json()
    assert body['correct'] is False and body['xp'] == 0
    assert _progress(engine, sid)['status'] == 'ACTIVE'


def test_correct_flag_completes_lab_and_cannot_be_replayed(engine):
    sid = _sid(engine)
    body = engine.post('/api/lab-engine/submit-flag', json={'session_id': sid, 'flag': FLAG}).get_json()
    assert body['correct'] is True and body['xp'] == 100
    prog = _progress(engine, sid)
    assert prog['status'] == 'COMPLETED' and prog['score'] == 100
    again = engine.post('/api/lab-engine/submit-flag', json={'session_id': sid, 'flag': FLAG})
    assert again.status_code == 400                           # session no longer active
    assert _progress(engine, sid)['score'] == 100


# ---------------------------------------------------------------------- hints
def test_hint_costs_xp_but_never_goes_negative(engine):
    sid = _sid(engine)
    body = engine.post('/api/lab-engine/hint', json={'session_id': sid, 'mission_id': M1}).get_json()
    assert body['success'] and body['hint_text'] == 'first hint' and body['total_hints'] == 2
    assert _progress(engine, sid)['score'] == 0               # floor at zero
    _answer(engine, sid, M1, Q1, 'sqli')                      # +50
    engine.post('/api/lab-engine/hint', json={'session_id': sid, 'mission_id': M1, 'hint_index': 1})
    prog = _progress(engine, sid)
    assert prog['score'] == 40 and prog['hints_used'] == 2    # 50 - 10


def test_server_controls_hint_order_and_charges_once(engine):
    sid = _sid(engine)
    _answer(engine, sid, M1, Q1, 'sqli')                       # +50 so charges are visible
    ask = lambda **kw: engine.post('/api/lab-engine/hint',
                                   json={'session_id': sid, 'mission_id': M1, **kw}).get_json()
    # A client-chosen index can't skip ahead: the first request always gets hint 0.
    first = ask(hint_index=1)
    assert first['hint_text'] == 'first hint' and first['hint_index'] == 0
    assert _progress(engine, sid)['score'] == 45               # charged 5, once
    # Re-reading a hint that was already paid for is free.
    again = ask(hint_index=0)
    assert again['hint_text'] == 'first hint'
    assert _progress(engine, sid)['score'] == 45
    second = ask()
    assert second['hint_text'] == 'second hint' and _progress(engine, sid)['score'] == 35
    assert ask()['success'] is False                           # nothing left to reveal
    assert _progress(engine, sid)['hints_used'] == 2


def test_hint_edge_cases(engine):
    sid = _sid(engine)
    locked = engine.post('/api/lab-engine/hint', json={'session_id': sid, 'mission_id': M2})
    assert locked.status_code == 403                           # locked mission: no peeking ahead
    assert engine.post('/api/lab-engine/hint', json={'session_id': sid}).status_code == 400
    with app.app_context():
        _add_lab('ulab-other', 9)
        db.session.commit()
    foreign = engine.post('/api/lab-engine/hint',
                          json={'session_id': sid, 'mission_id': 'ulab-other_m1'})
    assert foreign.status_code in (403, 404)                   # another lab's mission


# ----------------------------------------------------------------------- stop
def test_stop_expires_session_and_blocks_further_answers(engine):
    sid = _sid(engine)
    assert engine.post('/api/lab-engine/stop', json={'session_id': sid}).get_json()['success']
    assert _progress(engine, sid)['status'] == 'EXPIRED'
    assert _answer(engine, sid, M1, Q1, 'sqli').status_code == 400
    assert engine.post('/api/lab-engine/stop', json={}).status_code == 400


# ------------------------------------------------------------- per-user flags
def test_templated_flag_is_unique_per_user(engine, other_client):
    from services.flags import user_flag_tag
    with app.app_context():
        flag = models.UploadedLabFlag.query.filter_by(lab_id=LAB).first()
        flag.flag_value = 'FLAG{dyn_{{TAG}}}'
        uid_me = models.User.query.filter_by(username='testuser').first().id
        uid_other = models.User.query.filter_by(username='intruder1').first().id
        mine = f"FLAG{{dyn_{user_flag_tag(app.config['SECRET_KEY'], uid_me, LAB)}}}"
        theirs = f"FLAG{{dyn_{user_flag_tag(app.config['SECRET_KEY'], uid_other, LAB)}}}"
        db.session.commit()
    assert mine != theirs
    sid_me, sid_other = _sid(engine), _sid(other_client)
    submit = lambda c, sid, f: c.post('/api/lab-engine/submit-flag',
                                      json={'session_id': sid, 'flag': f}).get_json()
    assert submit(other_client, sid_other, mine)['correct'] is False   # a leaked flag is useless
    assert submit(engine, sid_me, 'FLAG{dyn_{{TAG}}}')['correct'] is False  # literal template isn't accepted
    assert submit(engine, sid_me, mine)['correct'] is True
