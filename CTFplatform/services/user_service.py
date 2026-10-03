from sqlalchemy import func

from extensions import db
from models import User


def get_user_by_username(username):
    """Case-insensitive lookup: 'Admin' and 'admin' are the same account."""
    name = (username or '').strip().lower()
    if not name:
        return None
    return User.query.filter(func.lower(User.username) == name).first()


def create_user(username, hashed_password, email=None):
    new_user = User(username=username, password=hashed_password, email=email)
    db.session.add(new_user)
    db.session.flush() # Flush to get the ID without committing
    return new_user.id
