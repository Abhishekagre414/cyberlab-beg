from unittest import mock

import pytest

from services import docker_service as ds
from services.flags import expand_flag, user_flag_tag


def test_flag_tag_is_stable_and_scoped():
    a = user_flag_tag('secret', 1, 'lab-a')
    assert a == user_flag_tag('secret', 1, 'lab-a')              # deterministic
    assert len(a) == 12
    assert a != user_flag_tag('secret', 2, 'lab-a')              # per user
    assert a != user_flag_tag('secret', 1, 'lab-b')              # per lab
    assert a != user_flag_tag('other-secret', 1, 'lab-a')        # bound to the server secret


def test_expand_flag():
    assert expand_flag('FLAG{x_{{TAG}}}', 'abc') == 'FLAG{x_abc}'
    assert expand_flag('FLAG{static}', 'abc') == 'FLAG{static}'  # untouched without the token


def test_oversized_body_rejected_outside_admin(client):
    big = 'x' * (3 * 1024 * 1024)
    assert client.post('/login', data={'username': 'a', 'password': big}).status_code == 413
    assert client.post('/api/evidence', data=big, content_type='application/json').status_code == 413


def _client_with_container(monkeypatch, tmp_path):
    (tmp_path / 'Dockerfile').write_text('FROM scratch')
    client = mock.MagicMock()
    client.containers.run.return_value = mock.MagicMock(id='abc123', status='running')
    monkeypatch.setattr(ds, 'get_docker_client', lambda: client)
    return client


def test_uploaded_lab_uses_restricted_network_and_gets_tag(monkeypatch, tmp_path):
    client = _client_with_container(monkeypatch, tmp_path)
    port, cid, msg = ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {}, flag_tag='t4g')
    assert msg == 'Success', msg
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs['network'] == ds.LAB_NETWORK_NAME
    assert kwargs['environment']['LAB_FLAG_TAG'] == 't4g'
    assert ds.LAB_NETWORK_OPTIONS['com.docker.network.bridge.enable_ip_masquerade'] == 'false'
    assert ds.LAB_NETWORK_OPTIONS['com.docker.network.bridge.enable_icc'] == 'false'
    ds._allocated_ports.discard(port)


def test_lab_refused_if_restricted_network_cannot_be_created(monkeypatch, tmp_path):
    client = _client_with_container(monkeypatch, tmp_path)
    class NotFound(Exception):
        pass
    client.networks.get.side_effect = NotFound('missing')
    client.networks.create.side_effect = RuntimeError('boom')
    monkeypatch.setattr(ds, 'ALLOW_OPEN_LAB_NETWORK', False)
    port, cid, msg = ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {})
    assert port is None and cid is None and 'restricted lab network' in msg
    client.containers.run.assert_not_called()                    # fail closed: no lab with internet access


def test_lab_ports_follow_bind_and_public_host_settings(monkeypatch, tmp_path):
    monkeypatch.setenv('LAB_BIND_ADDR', '0.0.0.0')
    monkeypatch.setenv('LAB_PUBLIC_HOST', 'labs.example.org')
    client = _client_with_container(monkeypatch, tmp_path)
    port, _, msg = ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {})
    assert msg == 'Success', msg
    assert all(v[0] == '0.0.0.0' for v in client.containers.run.call_args.kwargs['ports'].values())
    assert ds.lab_target_url(port) == f'http://labs.example.org:{port}'
    ds._allocated_ports.discard(port)


def test_defaults_are_loopback_only(monkeypatch):
    monkeypatch.delenv('LAB_BIND_ADDR', raising=False)
    monkeypatch.delenv('LAB_PUBLIC_HOST', raising=False)
    assert ds.lab_bind_addr() == '127.0.0.1'
    assert ds.lab_target_url(12345) == 'http://127.0.0.1:12345'


def test_container_that_never_runs_is_reported_and_cleaned_up(monkeypatch, tmp_path):
    client = _client_with_container(monkeypatch, tmp_path)
    client.containers.run.return_value = mock.MagicMock(id='x', status='exited')
    client.containers.run.return_value.logs.return_value = b'Traceback: boom'
    port, cid, msg = ds.start_uploaded_lab_container('lab', 'sess', str(tmp_path), {})
    assert port is None and 'did not start' in msg and 'boom' in msg
    client.containers.run.return_value.remove.assert_called()


def test_is_lab_running_uses_docker_api_not_loopback(monkeypatch):
    # Inside compose the web container's 127.0.0.1 is not the host, so the
    # check must go through the Docker API.
    monkeypatch.setattr(ds, 'get_uploaded_lab_container_status',
                        lambda sid, cid: {'status': 'running'})
    assert ds.is_lab_running('s', 'cid', 12345) is True
    monkeypatch.setattr(ds, 'get_uploaded_lab_container_status',
                        lambda sid, cid: {'status': 'exited'})
    assert ds.is_lab_running('s', 'cid', 12345) is False
    assert ds.is_lab_running('s', None, 12345) is False
