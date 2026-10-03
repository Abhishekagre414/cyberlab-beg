#!/usr/bin/env python3
"""End-to-end smoke test for a running deployment (stdlib only).

    python3 scripts/smoke_test.py https://your.domain
    python3 scripts/smoke_test.py http://localhost --insecure     # self-signed cert

Checks: health, login page, register + login, dashboard, published labs list,
starting one lab, reaching it on its published port, stopping it. Exit code 0
only if everything passed.
"""
import http.cookiejar
import json
import re
import secrets
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost').rstrip('/')
insecure = '--insecure' in sys.argv
ctx = ssl.create_default_context()
if insecure:
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                                     urllib.request.HTTPSHandler(context=ctx))
failures = []


def check(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + (f'  ({detail})' if detail and not ok else ''))
    if not ok:
        failures.append(name)
    return ok


def req(path, data=None, headers=None, method=None, as_json=False):
    h = dict(headers or {})
    body = None
    if data is not None:
        if as_json:
            body = json.dumps(data).encode()
            h['Content-Type'] = 'application/json'
        else:
            body = urllib.parse.urlencode(data).encode()
    r = urllib.request.Request(base + path, data=body, headers=h, method=method)
    try:
        with opener.open(r, timeout=20) as resp:
            return resp.status, resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def csrf(html):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html) or re.search(r'csrfToken\s*=\s*"([^"]+)"', html)
    return m.group(1) if m else ''


print(f'Smoke test against {base}')
code, body = req('/health')
check('health endpoint', code == 200, code)
code, body = req('/login')
check('login page loads', code == 200 and 'csrf_token' in body, code)

user, pw = 'smoke' + secrets.token_hex(3), 'Smoke-' + secrets.token_hex(6)
code, body = req('/register')
code, body = req('/register', {'csrf_token': csrf(body), 'username': user, 'password': pw, 'confirm_password': pw})
check('register', code in (200, 302) and 'Invalid' not in body, code)
code, body = req('/dashboard')
check('logged in (dashboard)', code == 200 and 'login' not in body[:400].lower(), code)

code, body = req('/interactive-labs')
lab_ids = list(dict.fromkeys(re.findall(r'ulab-[0-9a-f]+', body)))
check('published labs are listed', code == 200 and len(lab_ids) >= 1, f'found {len(lab_ids)}')

if lab_ids:
    code, page = req(f'/interactive-lab/{lab_ids[0]}/play')
    token = csrf(page) or csrf(body)
    code, resp = req('/api/lab-engine/start', {'lab_id': lab_ids[0]}, {'X-CSRFToken': token}, as_json=True)
    try:
        data = json.loads(resp)
    except ValueError:
        data = {}
    check('lab starts', code == 200 and data.get('success'), f'{code} {resp[:200]}')
    url = data.get('target_url')
    if url:
        host, port = urllib.parse.urlparse(url).hostname, urllib.parse.urlparse(url).port
        try:
            with socket.create_connection((host, port), timeout=10):
                reachable = True
        except OSError as e:
            reachable, why = False, str(e)
        check(f'lab reachable at {url} from this machine', reachable,
              'not reachable from here - fine if you only test from the server; for remote learners set LAB_BIND_ADDR/LAB_PUBLIC_HOST and open the firewall' if not reachable else '')
        if reachable:
            try:
                with urllib.request.urlopen(url, timeout=10) as r:
                    check('lab app answers HTTP', r.status == 200)
            except Exception as e:  # noqa: BLE001
                check('lab app answers HTTP', False, e)
        sid = data.get('session_id')
        code, resp = req('/api/lab-engine/stop', {'session_id': sid}, {'X-CSRFToken': token}, as_json=True)
        check('lab stops', code == 200, code)

print()
if failures:
    print(f'{len(failures)} check(s) FAILED: ' + ', '.join(failures))
    sys.exit(1)
print('All checks passed.')
