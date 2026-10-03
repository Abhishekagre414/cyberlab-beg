import os
from unittest import mock

import pytest

from services import docker_service as ds


def test_hardening_profile_drops_privileges():
    h = ds.CONTAINER_HARDENING
    assert h['cap_drop'] == ['ALL']
    assert 'no-new-privileges:true' in h['security_opt']
    assert '/tmp' in h['tmpfs']


def test_native_fallback_disabled_by_default(monkeypatch, tmp_path):
    assert ds.ALLOW_NATIVE_LABS is False
    monkeypatch.setattr(ds, 'get_docker_client', lambda: None)
    popen = mock.Mock()
    monkeypatch.setattr('subprocess.Popen', popen)
    port, cid, msg = ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {})
    assert port is None and cid is None
    assert 'disabled' in msg.lower() or 'cannot be started' in msg.lower()
    popen.assert_not_called()  # nothing may be executed on the host


def test_native_fallback_never_receives_platform_secrets(monkeypatch, tmp_path):
    (tmp_path / 'app.py').write_text('print("hi")')
    monkeypatch.setattr(ds, 'get_docker_client', lambda: None)
    monkeypatch.setattr(ds, 'ALLOW_NATIVE_LABS', True)
    monkeypatch.setenv('SECRET_KEY', 'super-secret')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h/db')
    monkeypatch.setenv('ADMIN_PASSWORD', 'adminpw')
    monkeypatch.setenv('GEMINI_API_KEY', 'gem')
    captured = {}

    class FakeProc:
        pid = 4242
        def poll(self): return 1      # "exited" -> function returns failure quickly
        def terminate(self): pass

    def fake_popen(cmd, **kw):
        captured.update(kw)
        return FakeProc()

    monkeypatch.setattr('subprocess.Popen', fake_popen)
    ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {})
    env = captured['env']
    for secret in ('SECRET_KEY', 'DATABASE_URL', 'ADMIN_PASSWORD', 'GEMINI_API_KEY'):
        assert secret not in env
    assert set(env) <= set(ds._NATIVE_ENV_ALLOWLIST)


def test_uploaded_lab_container_started_with_hardening(monkeypatch, tmp_path):
    (tmp_path / 'Dockerfile').write_text('FROM scratch')
    client = mock.MagicMock()
    container = mock.MagicMock(id='abc123', status='running')
    client.containers.run.return_value = container
    monkeypatch.setattr(ds, 'get_docker_client', lambda: client)
    port, cid, msg = ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {})
    assert msg == 'Success', msg
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs['cap_drop'] == ['ALL']
    assert 'no-new-privileges:true' in kwargs['security_opt']
    assert kwargs['pids_limit'] > 0 and kwargs['mem_limit']
    # published only on loopback, never 0.0.0.0
    assert all(v[0] == '127.0.0.1' for v in kwargs['ports'].values())
    ds._allocated_ports.discard(port)


@pytest.mark.parametrize('bad', ['../etc', 'a/b', '', 'UP', '..'])
def test_manual_lab_container_rejects_bad_ids(bad):
    ip, msg = ds.start_lab_container(bad, 1)
    assert ip is None and msg == 'Invalid lab ID.'
