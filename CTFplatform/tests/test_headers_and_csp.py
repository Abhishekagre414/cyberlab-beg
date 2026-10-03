import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(__file__))


def _csp(client, path='/'):
    r = client.get(path)
    return r, r.headers.get('Content-Security-Policy', '')


def test_csp_has_no_unsafe_inline_for_scripts(client):
    _, csp = _csp(client)
    script_src = re.search(r"script-src ([^;]*)", csp).group(1)
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src
    assert "nonce-" in script_src


def test_csp_locks_down_other_vectors(client):
    _, csp = _csp(client)
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    assert "default-src 'self'" in csp


def test_inline_scripts_carry_the_response_nonce(client):
    r, csp = _csp(client, '/login')
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    html = r.data.decode()
    inline = re.findall(r'<script(?![^>]*\bsrc=)([^>]*)>', html)
    assert inline, "expected at least one inline script (csrf token)"
    assert all(f'nonce="{nonce}"' in attrs for attrs in inline)


def test_nonce_changes_per_request(client):
    n1 = re.search(r"'nonce-([^']+)'", _csp(client)[1]).group(1)
    n2 = re.search(r"'nonce-([^']+)'", _csp(client)[1]).group(1)
    assert n1 != n2


def test_no_inline_event_handlers_in_templates_or_js():
    pattern = re.compile(r'\son(click|submit|change|input|load|error|mouseover|keydown|keyup|focus|blur)\s*=', re.I)
    offenders = []
    for path in glob.glob(os.path.join(ROOT, 'templates', '**', '*.html'), recursive=True) + \
            glob.glob(os.path.join(ROOT, 'static', 'js', '*.js')):
        with open(path, encoding='utf-8', errors='ignore') as f:
            if pattern.search(f.read()):
                offenders.append(os.path.relpath(path, ROOT))
    assert offenders == [], f"inline handlers would be blocked by the CSP: {offenders}"


def test_every_inline_script_in_templates_has_nonce():
    offenders = []
    for path in glob.glob(os.path.join(ROOT, 'templates', '**', '*.html'), recursive=True):
        with open(path, encoding='utf-8', errors='ignore') as f:
            for m in re.finditer(r'<script(?![^>]*\bsrc=)([^>]*)>', f.read()):
                if 'nonce=' not in m.group(1):
                    offenders.append(os.path.relpath(path, ROOT))
    assert offenders == []


def test_basic_security_headers_present(client):
    r = client.get('/')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options')
    assert 'Referrer-Policy' in r.headers


def test_session_cookie_flags(client):
    from app import app
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert app.config['PERMANENT_SESSION_LIFETIME'] <= 24 * 3600
