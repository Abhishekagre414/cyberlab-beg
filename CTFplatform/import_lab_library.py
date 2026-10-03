"""Import the bundled labs in lab_library/ into the platform database.

    python import_lab_library.py            # import any that are missing, as drafts
    python import_lab_library.py --publish  # ...and publish them

Idempotent: a lab whose title already exists is skipped. Labs are imported in
learning-path order. Needs a writable data dir; see config.py (LAB_UPLOAD_DIR).
"""
import argparse
import os
import sys
import tempfile
import uuid

ORDER = ['techcorp-info-disclosure', 'techcorp-idor', 'techcorp-access-control',
         'support-desk', 'mail-center']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--publish', action='store_true')
    args = ap.parse_args()

    from app import app
    from extensions import db
    from models import UploadedLab
    from services.lab_parser_service import LabZipParser, save_manifest_to_db

    lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lab_library')
    with app.app_context():
        upload_dir = app.config.get('LAB_UPLOAD_DIR') or os.path.join(tempfile.gettempdir(), 'uploaded_labs')
        os.makedirs(upload_dir, exist_ok=True)
        parser = LabZipParser()
        for name in ORDER:
            zip_path = os.path.join(lib, f'{name}.zip')
            if not os.path.isfile(zip_path):
                print(f'[skip] {name}: zip not found')
                continue
            check = parser.validate_zip(zip_path)
            if not check.valid:
                print(f'[FAIL] {name}: {check.errors}')
                sys.exit(1)
            extract_dir = os.path.join(upload_dir, f'lab_{uuid.uuid4().hex[:12]}')
            manifest = parser.parse_zip(zip_path, extract_dir)
            if UploadedLab.query.filter_by(title=manifest.title).first():
                print(f'[skip] {manifest.title}: already imported')
                continue
            lab = save_manifest_to_db(manifest, extract_dir)
            if args.publish:
                lab.status = 'published'
            db.session.commit()
            print(f'[ok]   {lab.title} ({lab.status}) -> {lab.id}')


if __name__ == '__main__':
    main()
