"""User registration and authentication logic.

Routes handle HTTP only, this module owns password and token rules.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


class UsernameTakenError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


def register_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UsernameTakenError(username) from exc
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    db.refresh(user)
    return user


def login_user(db: Session, username: str, password: str) -> str:
    try:
        user = db.query(User).filter(User.username == username).first()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError(username)
    return create_access_token(user.id)
