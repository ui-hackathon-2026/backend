"""Email authentication with rotating refresh tokens.

Access tokens live 15 minutes, refresh tokens 7 days. Refresh rotates:
each use revokes the old token and issues a fresh pair, replay of a
revoked token fails. Only token hashes touch the database.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.core.security import (
    ACCESS_EXPIRE_SECONDS,
    avatar_initials,
    aware,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import AuthSession, AuthTokens, AuthUser


class EmailTakenError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidRefreshError(ValueError):
    pass


def build_user(user: User) -> AuthUser:
    return AuthUser(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        avatarInitials=avatar_initials(user.name),
        createdAt=user.created_at,
    )


def store_refresh(db: Session, user_id: int) -> str:
    token, jti, expires_at = create_refresh_token(user_id)
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    return token


def issue_session(db: Session, user: User) -> AuthSession:
    try:
        access = create_access_token(user.id)
        refresh = store_refresh(db, user.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return AuthSession(
        user=build_user(user),
        tokens=AuthTokens(
            accessToken=access, refreshToken=refresh, expiresIn=ACCESS_EXPIRE_SECONDS
        ),
    )


def register_user(db: Session, name: str, email: str, password: str) -> AuthSession:
    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
        return issue_session(db, user)
    except IntegrityError as exc:
        db.rollback()
        raise EmailTakenError(email) from exc
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc


def login_user(db: Session, email: str, password: str) -> AuthSession:
    try:
        user = db.query(User).filter(User.email == email).first()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError(email)
    return issue_session(db, user)


def refresh_session(db: Session, refresh_token: str) -> AuthTokens:
    payload = decode_token(refresh_token, "refresh")
    if payload is None:
        raise InvalidRefreshError("bad token")
    try:
        row = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_token(refresh_token))
            .first()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    now = datetime.now(timezone.utc)
    if (
        row is None
        or row.revoked_at is not None
        or aware(row.expires_at) <= now
        or str(row.user_id) != str(payload.get("sub"))
    ):
        raise InvalidRefreshError("revoked")
    try:
        user = db.get(User, row.user_id)
        if user is None:
            raise InvalidRefreshError("gone")
        row.revoked_at = now
        access = create_access_token(user.id)
        refresh = store_refresh(db, user.id)
        db.commit()
    except InvalidRefreshError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return AuthTokens(
        accessToken=access, refreshToken=refresh, expiresIn=ACCESS_EXPIRE_SECONDS
    )


def logout_user(db: Session, refresh_token: str) -> None:
    try:
        row = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_token(refresh_token))
            .first()
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
