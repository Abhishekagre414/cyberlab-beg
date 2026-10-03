"""The five bundled labs must import cleanly and be solvable.

* manifest checks run everywhere (stdlib only);
* every answer is pushed through the real ValidationEngine;
* each lab's Flask app is loaded and its intended exploit path is driven with
  the test client (skipped if Flask isn't importable).
"""
import json
import os
import sys
import zipfile

import pytest

from services.lab_parser_service import LabZipParser
from services.lab_validation_service import ValidationEngine

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lab_library')
LABS = ['mail-center', 'support-desk', 'techcorp-access-control', 'techcorp-idor', 'techcorp-info-disclosure']


class Q:  # minimal stand-in for UploadedLabQuestion
    def __init__(self, d):
        self.validation_type = d.get('validation_type', 'ANSWER_MATCH')
        a = d['answer']
        self.expected_answer = json.dumps(a) if isinstance(a, list) else a
        self.case_sensitive = d.get('case_sensitive', False)


@pytest.fixture(scope='module', params=LABS)
def lab(request, tmp_path_factory):
    out = str(tmp_path_factory.mktemp(request.param))
    path = os.path.join(LIB, request.param + '.zip')
    parser = LabZipParser()
    assert parser.validate_zip(path).valid
    return request.param, parser.parse_zip(path, out), out


def test_manifest_is_complete(lab):
    name, m, _ = lab
    assert not m.title.isdigit() and len(m.title) > 10
    assert len(m.missions) == 5
    assert m.flags and m.flags[0]['flag_value'].startswith(('TECHCORP{', 'TC{'))
    assert m.docker_config['dockerfile_path'] == 'Dockerfile' and m.docker_config['ports'] == [5000]
    for mission in m.missions:
        assert mission['questions'] and mission['hints']
        for q in mission['questions']:
            assert q['answer']


def test_every_answer_is_accepted_and_wrong_is_rejected(lab):
    _, m, _ = lab
    for mission in m.missions:
        for q in mission['questions']:
            if q.get('validation_type') == 'REGEX':
                # free-text questions: a sensible learner answer must match
                samples = ['authorization', 'database', 'directory listing']
                assert any(ValidationEngine.validate_answer(x, Q(q)).correct for x in samples), mission['title']
            else:
                answers = q['answer'] if isinstance(q['answer'], list) else [q['answer']]
                for a in answers:
                    assert ValidationEngine.validate_answer(a, Q(q)).correct, (mission['title'], a)
            assert not ValidationEngine.validate_answer('definitely-wrong-zzz', Q(q)).correct


def test_lab_is_self_contained_and_safe(lab):
    _, _, out = lab
    files = [os.path.join(r, f) for r, _, fs in os.walk(out) for f in fs]
    assert not any(f.endswith(('.db', '.pyc')) for f in files)         # databases are rebuilt at image build
    assert not any(os.path.basename(f).upper().startswith('INSTRUCTOR') for f in files)  # no spoilers shipped
    df = open(os.path.join(out, 'Dockerfile')).read()
    assert 'USER lab' in df                                              # not root
    for f in files:
        if f.endswith('.py'):
            src = open(f).read()
            assert 'host="127.0.0.1"' not in src                         # unreachable inside a container


# ----------------------------------------------------------- run the real apps
@pytest.fixture
def lab_app(request, tmp_path):
    """Extract a bundled lab zip and import its Flask app under a UNIQUE module
    name, so the platform's own `app` module (used by other tests) is untouched."""
    import importlib.util
    name, entry = request.param
    d = tmp_path / name
    with zipfile.ZipFile(os.path.join(LIB, name + '.zip')) as zf:
        zf.extractall(d)
    script = d / entry / 'app.py'
    modname = 'lab_under_test_' + name.replace('-', '_')
    spec = importlib.util.spec_from_file_location(modname, script)
    mod = importlib.util.module_from_spec(spec)
    # Flask finds templates/static via sys.modules[__name__].__file__, so the
    # module must be registered or it silently falls back to the cwd.
    sys.modules[modname] = mod
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop(modname, None)


@pytest.mark.parametrize('lab_app', [('techcorp-idor', '')], indirect=True)
def test_idor_exploit_path(lab_app):
    lab_app.init_db()
    c = lab_app.app.test_client()
    c.post('/api/start-lab')
    c.post('/login', data={'username': 'alex', 'password': 'Alex@123'})
    assert b'TECHCORP{' not in c.get('/profile/101').data
    assert b'TECHCORP{idor_found}' in c.get('/profile/102').data
    assert c.post('/api/submit-flag', json={'flag': 'TECHCORP{idor_found}'}).get_json()['correct']


@pytest.mark.parametrize('lab_app', [('techcorp-access-control', '')], indirect=True)
def test_access_control_exploit_path(lab_app):
    lab_app.init_db()
    c = lab_app.app.test_client()
    c.post('/api/start-lab')
    c.post('/login', data={'username': 'alex', 'password': 'Alex@123'})
    denied = c.get('/admin')
    assert denied.status_code == 403 and b'TC{' not in denied.data
    c.set_cookie('role', 'administrator')
    assert b'TC{broken_access_control}' in c.get('/admin').data
    assert c.post('/api/submit-flag', json={'flag': 'TC{broken_access_control}'}).get_json()['correct']


@pytest.mark.parametrize('lab_app', [('techcorp-info-disclosure', '')], indirect=True)
def test_info_disclosure_exploit_path(lab_app):
    lab_app.init_db()
    lab_app.init_docs()
    c = lab_app.app.test_client()
    c.post('/api/start-lab')
    c.post('/login', data={'username': 'alex', 'password': 'Alex@123'})
    assert b'hr' in c.get('/files/').data
    assert b'employee_salary_report.txt' in c.get('/files/hr/').data
    assert b'TECHCORP{hidden_file_found}' in c.get('/files/hr/employee_salary_report.txt').data
    assert c.get('/files/../app.py').status_code in (400, 403, 404)       # sandbox still holds
    assert c.post('/api/submit-flag', json={'flag': 'TECHCORP{hidden_file_found}'}).get_json()['correct']


@pytest.mark.parametrize('lab_app,answers,flag', [
    (('mail-center', 'app'), ['Urgency', 'URL', 'User', 'Credentials', 'MFA'], 'TECHCORP{human_firewall}'),
    (('support-desk', 'app'), ['Browser', 'The user', 'Browser', 'Browser', 'Encoding'], 'TECHCORP{xss_ticket_found}'),
], indirect=['lab_app'])
def test_mission_quiz_labs(lab_app, answers, flag):
    c = lab_app.app.test_client()
    assert c.get('/').status_code == 200 and c.get('/lab').status_code == 200
    last = None
    for i, a in enumerate(answers, 1):
        assert not c.post(f'/api/mission/{i}', json={'answer': 'wrong'}).get_json()['ok']
        last = c.post(f'/api/mission/{i}', json={'answer': a}).get_json()
        assert last['ok']
    assert last['flag'] == flag
