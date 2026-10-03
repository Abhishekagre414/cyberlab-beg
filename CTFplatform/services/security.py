"""Small, dependency-free security helpers shared by the routes."""
import hmac
import os
import re
import zipfile

USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]{3,32}$')
EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$')
LAB_ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,39}$')

# A throw-away hash used to burn the same CPU time when a username does not
# exist, so response timing can't be used to enumerate valid usernames.
from werkzeug.security import generate_password_hash  # noqa: E402
DUMMY_PASSWORD_HASH = generate_password_hash('not-a-real-password')


def safe_equals(a, b):
    """Constant-time string comparison that never raises on odd input types."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def validate_username(username):
    if not username or not USERNAME_RE.match(username):
        return False, "Username must be 3-32 characters: letters, numbers, '.', '_' or '-'."
    return True, ""


def validate_email(email):
    if not email:
        return True, ""  # email is optional
    if not EMAIL_RE.match(email):
        return False, "Please enter a valid email address."
    return True, ""


def validate_password(password, username=""):
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password must be at most 128 characters long."
    if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        return False, "Password must contain at least one letter and one number."
    if username and password.lower() == username.lower():
        return False, "Password must not be the same as your username."
    return True, ""


def validate_lab_id(lab_id):
    return bool(lab_id) and bool(LAB_ID_RE.match(lab_id))


class UnsafeZipError(ValueError):
    pass


def safe_extract_zip(zip_file, dest_dir, max_total_size=500 * 1024 * 1024, max_files=10000):
    """Extract a ZIP with zip-slip, symlink, size and file-count protection.

    `zip_file` may be a path or a file-like object. Raises UnsafeZipError for
    anything suspicious *before* writing a single byte to disk.
    """
    dest_root = os.path.realpath(dest_dir)
    with zipfile.ZipFile(zip_file, 'r') as zf:
        infos = zf.infolist()
        if len(infos) > max_files:
            raise UnsafeZipError(f"ZIP has too many files (max {max_files}).")
        total = 0
        for info in infos:
            total += info.file_size
            if total > max_total_size:
                raise UnsafeZipError("ZIP expands to more than the allowed size.")
            name = info.filename
            if name.startswith(('/', '\\')) or '\x00' in name:
                raise UnsafeZipError(f"Unsafe path in ZIP: {name!r}")
            # Unix symlink bit in external_attr -> refuse, symlinks can escape.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise UnsafeZipError(f"Symlinks are not allowed in ZIP: {name!r}")
            target = os.path.realpath(os.path.join(dest_root, name))
            if target != dest_root and not target.startswith(dest_root + os.sep):
                raise UnsafeZipError(f"Path traversal attempt in ZIP: {name!r}")
        zf.extractall(dest_root)
