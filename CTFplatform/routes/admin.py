from flask import Blueprint, render_template, session, redirect, url_for, abort
from extensions import db
from models import User, AuditLog, ManualLab, ManualLabProgress, ManualLabFlag
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def is_admin():
    if 'user_id' not in session:
        return False
    user = User.query.get(session['user_id'])
    return user and user.role == 'admin'

@admin_bp.before_request
def check_admin():
    if not is_admin():
        abort(403)

def _render_dashboard(error=None, status=200):
    users = User.query.filter_by(role='student').all()
    logs_data = db.session.query(
        AuditLog.id, User.username, AuditLog.action, AuditLog.details, AuditLog.timestamp
    ).outerjoin(User, AuditLog.user_id == User.id).order_by(AuditLog.timestamp.desc()).limit(50).all()
    logs = [{'id': l.id, 'username': l.username, 'action': l.action,
             'details': l.details, 'timestamp': l.timestamp} for l in logs_data]
    manual_labs = ManualLab.query.all()
    return render_template('admin.html', title="Admin Dashboard", users=users, logs=logs,
                           manual_labs=manual_labs, error=error), status


@admin_bp.route('/')
def dashboard():
    return _render_dashboard()

@admin_bp.route('/lab', methods=['POST'])
def add_lab():
    import os
    import shutil
    from flask import request, current_app
    from services.notification_service import notify_all_users_new_lab
    from services.audit_service import log_action
    from services.security import validate_lab_id, safe_extract_zip, UnsafeZipError
    import zipfile

    lab_id = (request.form.get('lab_id') or '').strip()
    name = request.form.get('name')
    topic = request.form.get('topic')
    difficulty = request.form.get('difficulty')
    target_type = request.form.get('target_type')
    flag_value = request.form.get('flag_value')
    lab_zip = request.files.get('lab_zip')

    # lab_id becomes a directory name, so it must be a plain slug. Without this
    # a value like "../../etc" escaped the labs directory.
    if not validate_lab_id(lab_id):
        return _render_dashboard(
            "Lab ID must be 2-40 characters: lowercase letters, numbers, '-' or '_'.", 400)

    if ManualLab.query.get(lab_id):
        return _render_dashboard("Lab ID already exists.", 400)

    if not flag_value or not lab_zip or lab_zip.filename == '':
        return _render_dashboard("Lab flag and ZIP file are required.", 400)

    if not lab_zip.filename.lower().endswith('.zip'):
        return _render_dashboard("Only .zip files are allowed.", 400)

    labs_root = os.path.realpath(os.path.join(current_app.root_path, 'labs'))
    labs_dir = os.path.realpath(os.path.join(labs_root, lab_id))
    if os.path.dirname(labs_dir) != labs_root:  # belt and braces
        return _render_dashboard("Invalid lab ID.", 400)
    os.makedirs(labs_dir, exist_ok=True)

    try:
        safe_extract_zip(
            lab_zip, labs_dir,
            max_total_size=current_app.config.get('LAB_MAX_ZIP_DECOMPRESSED_SIZE', 500 * 1024 * 1024),
            max_files=current_app.config.get('LAB_MAX_ZIP_FILE_COUNT', 10000),
        )
    except zipfile.BadZipFile:
        shutil.rmtree(labs_dir, ignore_errors=True)
        return _render_dashboard("Invalid ZIP file uploaded.", 400)
    except UnsafeZipError as e:
        shutil.rmtree(labs_dir, ignore_errors=True)
        return _render_dashboard(f"Rejected ZIP: {e}", 400)

    new_lab = ManualLab(id=lab_id, name=name, topic=topic, difficulty=difficulty, target_type=target_type)
    db.session.add(new_lab)
    db.session.add(ManualLabFlag(manual_lab_id=lab_id, flag_value=flag_value))

    log_action(session['user_id'], 'ADMIN_ADD_LAB', f"Lab: {lab_id}")
    db.session.commit()

    notify_all_users_new_lab(name, topic)
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/manual-lab/<lab_id>/delete', methods=['POST'])
def manual_lab_delete(lab_id):
    import shutil
    import os
    from flask import current_app, flash
    from services.audit_service import log_action

    lab = ManualLab.query.get(lab_id)
    if not lab:
        return redirect(url_for('admin.dashboard'))

    # Delete associated progress and flags
    ManualLabProgress.query.filter_by(manual_lab_id=lab_id).delete()
    ManualLabFlag.query.filter_by(manual_lab_id=lab_id).delete()
    
    db.session.delete(lab)
    db.session.commit()
    
    # Delete the extracted lab files from the filesystem
    from services.security import validate_lab_id
    labs_root = os.path.realpath(os.path.join(current_app.root_path, 'labs'))
    labs_dir = os.path.realpath(os.path.join(labs_root, lab_id))
    if validate_lab_id(lab_id) and os.path.dirname(labs_dir) == labs_root and os.path.isdir(labs_dir):
        shutil.rmtree(labs_dir)

    log_action(session['user_id'], 'ADMIN_DELETE_MANUAL_LAB', f"Lab: {lab_id}")
    return redirect(url_for('admin.dashboard'))


# =========================================================================
# ZIP-to-Interactive Lab Engine — Admin Routes
# =========================================================================

@admin_bp.route('/labs/upload', methods=['GET'])
def lab_upload_page():
    """Show the lab ZIP upload page."""
    from models import UploadedLab
    uploaded_labs = UploadedLab.query.order_by(UploadedLab.created_at.desc()).all()
    return render_template('admin_lab_upload.html', title="Upload Lab", uploaded_labs=uploaded_labs)


@admin_bp.route('/labs/upload', methods=['POST'])
def lab_upload():
    """Handle lab ZIP upload, parse it, and redirect to preview."""
    import os
    import tempfile
    from flask import request, current_app, jsonify
    from services.lab_parser_service import LabZipParser, save_manifest_to_db
    from services.audit_service import log_action

    from werkzeug.utils import secure_filename
    from config import IS_SERVERLESS
    from services.security import UnsafeZipError

    # Vercel's request body cap (~4.5MB) and ephemeral /tmp mean uploaded
    # labs can neither arrive nor persist there. Say so instead of failing
    # with an opaque platform error.
    if IS_SERVERLESS:
        return jsonify({'success': False,
                        'message': 'Lab uploads are not supported on this serverless deployment. '
                                   'Deploy with Docker Compose on a server to upload labs.'}), 501

    lab_zip = request.files.get('lab_zip')
    if not lab_zip or lab_zip.filename == '':
        return jsonify({'success': False, 'message': 'No ZIP file uploaded.'}), 400

    if not lab_zip.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'message': 'Only .zip files are allowed.'}), 400

    # Check file size
    max_size = current_app.config.get('LAB_UPLOAD_MAX_SIZE', 100 * 1024 * 1024)
    lab_zip.seek(0, 2)  # Seek to end
    size = lab_zip.tell()
    lab_zip.seek(0)  # Reset
    if size > max_size:
        return jsonify({'success': False,
                        'message': f'File too large. Maximum size: {max_size // (1024*1024)}MB'}), 400

    # Save ZIP to temp location
    upload_dir = current_app.config.get('LAB_UPLOAD_DIR',
                                         os.path.join(current_app.root_path, 'data', 'uploaded_labs'))
    os.makedirs(upload_dir, exist_ok=True)

    # Save the ZIP file temporarily
    # secure_filename blocks '../' path traversal in the uploaded name.
    temp_zip_path = os.path.join(upload_dir, f'temp_{secure_filename(lab_zip.filename) or "upload.zip"}')
    lab_zip.save(temp_zip_path)

    try:
        # Initialize parser with config limits
        parser = LabZipParser(
            max_decompressed_size=current_app.config.get('LAB_MAX_ZIP_DECOMPRESSED_SIZE', 500*1024*1024),
            max_file_count=current_app.config.get('LAB_MAX_ZIP_FILE_COUNT', 10000),
        )

        # Validate
        validation = parser.validate_zip(temp_zip_path)
        if not validation.valid:
            os.remove(temp_zip_path)
            return jsonify({
                'success': False,
                'message': 'ZIP validation failed.',
                'validation': validation.to_dict(),
            }), 400

        # Parse and extract
        import uuid
        extract_dir = os.path.join(upload_dir, f'lab_{uuid.uuid4().hex[:12]}')
        manifest = parser.parse_zip(temp_zip_path, extract_dir)

        # Save to database
        lab = save_manifest_to_db(manifest, extract_dir, user_id=session.get('user_id'))
        db.session.commit()

        log_action(session['user_id'], 'ADMIN_UPLOAD_LAB', f"Lab: {lab.id} ({lab.title})")

        # Clean up temp ZIP
        os.remove(temp_zip_path)

        return jsonify({
            'success': True,
            'message': 'Lab uploaded and parsed successfully.',
            'lab_id': lab.id,
            'validation': validation.to_dict(),
            'manifest': manifest.to_dict(),
            'redirect': url_for('admin.lab_preview', lab_id=lab.id),
        })

    except UnsafeZipError as e:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        return jsonify({'success': False, 'message': f'Rejected ZIP: {e}'}), 400
    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error processing ZIP: {str(e)}'}), 500


@admin_bp.route('/labs/<lab_id>/preview')
def lab_preview(lab_id):
    """Show the lab preview page before publishing."""
    import json
    from models import UploadedLab
    lab = UploadedLab.query.get_or_404(lab_id)
    missions = lab.missions
    flags = lab.flags

    # Parse docker config
    docker_config = {}
    if lab.docker_config:
        try:
            docker_config = json.loads(lab.docker_config)
        except json.JSONDecodeError:
            pass

    return render_template('admin_lab_preview.html',
                           title=f"Preview: {lab.title}",
                           lab=lab,
                           missions=missions,
                           flags=flags,
                           docker_config=docker_config)


@admin_bp.route('/labs/<lab_id>/publish', methods=['POST'])
def lab_publish(lab_id):
    """Publish a lab to make it visible to learners."""
    from models import UploadedLab
    from services.audit_service import log_action

    lab = UploadedLab.query.get_or_404(lab_id)
    lab.status = 'published'
    db.session.commit()

    log_action(session['user_id'], 'ADMIN_PUBLISH_LAB', f"Lab: {lab_id} ({lab.title})")

    return redirect(url_for('admin.lab_preview', lab_id=lab_id))


@admin_bp.route('/labs/<lab_id>/unpublish', methods=['POST'])
def lab_unpublish(lab_id):
    """Unpublish a lab (set to draft)."""
    from models import UploadedLab
    from services.audit_service import log_action

    lab = UploadedLab.query.get_or_404(lab_id)
    lab.status = 'draft'
    db.session.commit()

    log_action(session['user_id'], 'ADMIN_UNPUBLISH_LAB', f"Lab: {lab_id}")
    return redirect(url_for('admin.lab_preview', lab_id=lab_id))


@admin_bp.route('/labs/<lab_id>/delete', methods=['POST'])
def lab_delete(lab_id):
    """Delete an uploaded lab and its files."""
    import os
    import shutil
    from models import UploadedLab
    from services.audit_service import log_action

    lab = UploadedLab.query.get_or_404(lab_id)

    # Remove extracted files
    if lab.zip_path and os.path.isdir(lab.zip_path):
        try:
            shutil.rmtree(lab.zip_path)
        except Exception:
            pass

    db.session.delete(lab)
    db.session.commit()

    log_action(session['user_id'], 'ADMIN_DELETE_LAB', f"Lab: {lab_id}")
    return redirect(url_for('admin.lab_upload_page'))

