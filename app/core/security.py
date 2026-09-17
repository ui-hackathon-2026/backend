import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()

ACCESS_EXPIRE_SECONDS = 900
REFRESH_EXPIRE_DAYS = 7


def hash_password(plain: str) -> str:
    return password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def avatar_initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def encode_token(user_id: int, typ: str, expires: datetime) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "typ": typ, "iat": now, "exp": expires},
        settings.secret_key,
        algorithm="HS256",
    )


def create_access_token(user_id: int) -> str:
    return encode_token(
        user_id,
        "access",
        datetime.now(timezone.utc) + timedelta(seconds=ACCESS_EXPIRE_SECONDS),
    )


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    jti = secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=REFRESH_EXPIRE_DAYS)
    token = jwt.encode(
        {"sub": str(user_id), "typ": "refresh", "jti": jti, "iat": now, "exp": expires_at},
        settings.secret_key,
        algorithm="HS256",
    )
    return token, jti, expires_at


def decode_token(token: str, expected_typ: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != expected_typ:
        return None
    return payload


def aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment
