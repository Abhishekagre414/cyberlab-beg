"""Tests for the ZIP-to-lab parser (services/lab_parser_service.py).

Pure stdlib + tmp_path: no app or database needed except the last test.
"""
import io
import json
import os
import zipfile

import pytest

from services.lab_parser_service import LabZipParser
from services.security import UnsafeZipError

LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lab_library')

META = {
    "title": "Test Lab", "category": "Web", "difficulty": "Beginner",
    "storyline": "A long enough storyline for the detector to accept.",
    "flag": "FLAG{unit_test}",
    "missions": [
        {"mission_number": 2, "title": "Second", "points": 40,
         "hints": ["just a string hint"],
         "questions": [{"question": "q2", "answer": "b", "xp_reward": 5}]},
        {"mission_number": 1, "title": "First", "instructions": "do one thing",
         "questions": ["bare question"]},
    ],
}


def make_zip(tmp_path, entries, name='lab.zip'):
    path = tmp_path / name
    with zipfile.ZipFile(path, 'w') as zf:
        for member, data in entries.items():
            zf.writestr(member, data)
    return str(path)


def good_entries(**overrides):
    entries = {
        'metadata.json': json.dumps(META),
        'Dockerfile': 'FROM python:3.11\nCMD ["python", "app.py"]\n',
        'app.py': 'print("hi")',
    }
    entries.update(overrides)
    return entries


# ------------------------------------------------------------------ validate_zip
def test_valid_zip_passes(tmp_path):
    result = LabZipParser().validate_zip(make_zip(tmp_path, good_entries()))
    assert result.valid, result.errors


def test_missing_file_and_non_zip(tmp_path):
    parser = LabZipParser()
    assert not parser.validate_zip(str(tmp_path / 'nope.zip')).valid
    bad = tmp_path / 'bad.zip'
    bad.write_text('definitely not a zip')
    result = parser.validate_zip(str(bad))
    assert not result.valid and 'valid_zip' in result.checks


@pytest.mark.parametrize('evil', ['../evil.txt', '/etc/passwd', 'a/../../b.txt'])
def test_path_traversal_rejected_by_validation(tmp_path, evil):
    result = LabZipParser().validate_zip(make_zip(tmp_path, good_entries(**{evil: 'x'})))
    assert not result.valid
    assert result.checks['path_safety']['passed'] is False


def test_file_count_limit(tmp_path):
    entries = {f'f{i}.txt': 'x' for i in range(5)}
    result = LabZipParser(max_file_count=3).validate_zip(make_zip(tmp_path, entries))
    assert not result.valid and result.checks['file_count']['passed'] is False


def test_decompressed_size_limit(tmp_path):
    result = LabZipParser(max_decompressed_size=100).validate_zip(
        make_zip(tmp_path, good_entries(big='A' * 5000)))
    assert not result.valid and result.checks['decompressed_size']['passed'] is False


def test_blocked_extension_rejected(tmp_path):
    result = LabZipParser().validate_zip(make_zip(tmp_path, good_entries(**{'run.exe': 'MZ'})))
    assert not result.valid and result.checks['file_types']['passed'] is False


# -------------------------------------------------------------------- parse_zip
def test_parse_metadata_json_manifest(tmp_path):
    manifest = LabZipParser().parse_zip(make_zip(tmp_path, good_entries()), str(tmp_path / 'out'))
    assert manifest.title == 'Test Lab'
    assert manifest.lab_id.startswith('ulab-')
    assert [m['mission_number'] for m in manifest.missions] == [1, 2]   # sorted
    first, second = manifest.missions
    assert first['instructions'] == ['do one thing']                    # str -> list
    assert first['questions'][0]['question'] == 'bare question'
    assert second['hints'] == [{'hint_text': 'just a string hint', 'xp_cost': 10}]
    assert second['questions'][0]['xp_reward'] == 5
    assert manifest.flags[0]['flag_value'] == 'FLAG{unit_test}'
    assert manifest.docker_config['has_dockerfile'] is True
    # total = mission points (100 default + 40) + one flag (100 default)
    assert manifest.total_points == 100 + 40 + 100


def test_parse_refuses_unsafe_archive_before_writing(tmp_path):
    zip_path = make_zip(tmp_path, {'../escape.txt': 'x', 'metadata.json': '{}'})
    out = tmp_path / 'out'
    with pytest.raises(UnsafeZipError):
        LabZipParser().parse_zip(zip_path, str(out))
    assert not (tmp_path / 'escape.txt').exists()


def test_parse_enforces_size_limit(tmp_path):
    with pytest.raises(UnsafeZipError):
        LabZipParser(max_decompressed_size=50).parse_zip(
            make_zip(tmp_path, good_entries(big='A' * 5000)), str(tmp_path / 'out'))


def test_single_root_folder_is_detected(tmp_path):
    entries = {f'mylab/{k}': v for k, v in good_entries().items()}
    manifest = LabZipParser().parse_zip(make_zip(tmp_path, entries), str(tmp_path / 'out'))
    assert manifest.title == 'Test Lab'


def test_corrupt_metadata_json_does_not_crash(tmp_path):
    manifest = LabZipParser().parse_zip(
        make_zip(tmp_path, good_entries(**{'metadata.json': '{not json'})), str(tmp_path / 'out'))
    assert manifest.title  # falls back to defaults / other sources, never raises


@pytest.mark.parametrize('name', sorted(os.listdir(LIB_DIR)) if os.path.isdir(LIB_DIR) else [])
def test_shipped_library_labs_validate_and_parse(tmp_path, name):
    path = os.path.join(LIB_DIR, name)
    parser = LabZipParser()
    assert parser.validate_zip(path).valid
    manifest = parser.parse_zip(path, str(tmp_path / 'out'))
    assert manifest.missions and manifest.docker_config.get('has_dockerfile')


# ---------------------------------------------------------------- save to the DB
def test_save_manifest_to_db(client, tmp_path):
    import models
    from app import app
    from services.lab_parser_service import save_manifest_to_db
    manifest = LabZipParser().parse_zip(make_zip(tmp_path, good_entries()), str(tmp_path / 'out'))
    with app.app_context():
        lab = save_manifest_to_db(manifest, str(tmp_path / 'out'))
        models.db.session.commit()
        assert lab.status == 'draft'                       # never auto-published
        assert lab.sort_order == 1
        assert len(lab.missions) == 2
        assert models.UploadedLabFlag.query.filter_by(lab_id=lab.id).count() == 1
        assert models.UploadedLabHint.query.count() == 1
        assert models.UploadedLabQuestion.query.count() == 2
