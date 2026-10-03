import io
import os
import shutil
import stat
import zipfile

import pytest

import models
from extensions import db
from services.security import (UnsafeZipError, safe_extract_zip, validate_lab_id)


def _zip_bytes(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, data in entries.items():
            z.writestr(name, data)
    buf.seek(0)
    return buf


@pytest.fixture
def admin_client(client):
    from werkzeug.security import generate_password_hash
    from app import app
    with app.app_context():
        u = models.User(username='root1', password=generate_password_hash('adminpass1'), role='admin')
        db.session.add(u)
        db.session.commit()
        uid = u.id
    with client.session_transaction() as sess:
        sess['user_id'] = uid
    return client


# ---------------------------------------------------------------- access control
def test_admin_requires_login(client):
    assert client.get('/admin/').status_code == 403
    assert client.post('/admin/lab', data={}).status_code == 403


def test_admin_forbidden_for_students(auth_client):
    client, _ = auth_client
    assert client.get('/admin/').status_code == 403
    assert client.get('/admin/labs/upload').status_code == 403
    assert client.post('/admin/lab', data={}).status_code == 403


def test_admin_can_open_dashboard(admin_client):
    assert admin_client.get('/admin/').status_code == 200


# ---------------------------------------------------------------- lab id validation
@pytest.mark.parametrize('bad', ['../evil', '..', 'a/b', 'a\\b', '', 'A', 'x', '-lead', 'a' * 41, 'sp ace', '..%2f'])
def test_validate_lab_id_rejects(bad):
    assert not validate_lab_id(bad)


@pytest.mark.parametrize('good', ['mlab4', 'web-lab_01', 'ab'])
def test_validate_lab_id_accepts(good):
    assert validate_lab_id(good)


def _post_lab(client, lab_id, zip_buf, flag='FLAG{x}'):
    return client.post('/admin/lab', data={
        'lab_id': lab_id, 'name': 'N', 'topic': 'T', 'difficulty': 'Easy', 'target_type': 'web',
        'flag_value': flag, 'lab_zip': (zip_buf, 'lab.zip'),
    }, content_type='multipart/form-data')


def test_add_lab_rejects_path_traversal_id(admin_client):
    from app import app
    outside = os.path.realpath(os.path.join(app.root_path, 'labs', '..', 'pwned_dir'))
    r = _post_lab(admin_client, '../pwned_dir', _zip_bytes({'a.txt': 'x'}))
    assert r.status_code == 400
    assert not os.path.exists(outside)


def test_add_lab_rejects_zip_slip_and_cleans_up(admin_client):
    from app import app
    r = _post_lab(admin_client, 'slip-lab', _zip_bytes({'../../escaped.txt': 'x'}))
    assert r.status_code == 400
    assert b'Rejected ZIP' in r.data
    assert not os.path.exists(os.path.join(app.root_path, 'labs', 'slip-lab'))
    assert not os.path.exists(os.path.join(app.root_path, '..', 'escaped.txt'))
    with app.app_context():
        assert models.ManualLab.query.get('slip-lab') is None


def test_add_lab_rejects_non_zip_and_bad_zip(admin_client):
    assert _post_lab(admin_client, 'bad-one', io.BytesIO(b'not a zip')).status_code == 400
    r = admin_client.post('/admin/lab', data={
        'lab_id': 'txt-lab', 'name': 'N', 'topic': 'T', 'difficulty': 'E', 'target_type': 'web',
        'flag_value': 'F', 'lab_zip': (io.BytesIO(b'x'), 'lab.txt')}, content_type='multipart/form-data')
    assert r.status_code == 400


def test_add_lab_happy_path(admin_client):
    from app import app
    lab_dir = os.path.join(app.root_path, 'labs', 'good-lab')
    try:
        r = _post_lab(admin_client, 'good-lab', _zip_bytes({'Dockerfile': 'FROM scratch', 'app.py': 'print(1)'}))
        assert r.status_code == 302
        assert os.path.isfile(os.path.join(lab_dir, 'app.py'))
        with app.app_context():
            assert models.ManualLab.query.get('good-lab') is not None
        # duplicate id refused
        assert _post_lab(admin_client, 'good-lab', _zip_bytes({'a': 'b'})).status_code == 400
    finally:
        shutil.rmtree(lab_dir, ignore_errors=True)


# ---------------------------------------------------------------- safe_extract_zip
def test_extract_ok(tmp_path):
    safe_extract_zip(_zip_bytes({'d/a.txt': 'hi'}), str(tmp_path))
    assert (tmp_path / 'd' / 'a.txt').read_text() == 'hi'


@pytest.mark.parametrize('name', ['../x', 'a/../../x', '/abs/x', '\\win\\x'])
def test_extract_rejects_bad_paths(tmp_path, name):
    with pytest.raises(UnsafeZipError):
        safe_extract_zip(_zip_bytes({name: 'x'}), str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_extract_rejects_symlink(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        info = zipfile.ZipInfo('link')
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, '/etc/passwd')
    buf.seek(0)
    with pytest.raises(UnsafeZipError):
        safe_extract_zip(buf, str(tmp_path))


def test_extract_enforces_limits(tmp_path):
    many = _zip_bytes({f'f{i}.txt': 'x' for i in range(5)})
    with pytest.raises(UnsafeZipError):
        safe_extract_zip(many, str(tmp_path), max_files=3)
    big = _zip_bytes({'big.bin': 'A' * 5000})
    with pytest.raises(UnsafeZipError):
        safe_extract_zip(big, str(tmp_path), max_total_size=1000)


def test_admin_can_delete_uploaded_lab_and_its_files(admin_client, tmp_path):
    # lab_delete used `os` without importing it, so it raised NameError.
    from app import app
    lab_dir = tmp_path / 'extracted'
    lab_dir.mkdir()
    (lab_dir / 'f.txt').write_text('x')
    with app.app_context():
        db.session.add(models.UploadedLab(id='ulab-del', title='D', zip_path=str(lab_dir)))
        db.session.commit()
    r = admin_client.post('/admin/labs/ulab-del/delete')
    assert r.status_code == 302
    assert not lab_dir.exists()
    with app.app_context():
        assert models.UploadedLab.query.get('ulab-del') is None


def test_upload_route_rejects_path_traversal_zip(admin_client):
    r = admin_client.post('/admin/labs/upload', data={
        'lab_zip': (_zip_bytes({'../evil.txt': 'x', 'metadata.json': '{}'}), 'evil.zip')},
        content_type='multipart/form-data')
    assert r.status_code == 400
    assert r.get_json()['success'] is False
