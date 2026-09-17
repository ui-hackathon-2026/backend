from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

SessionDep = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer()


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or expired token",
    )


def get_current_user(
    db: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> User:
    payload = decode_token(credentials.credentials, "access")
    if payload is None:
        raise unauthorized()
    try:
        user = db.get(User, int(payload["sub"]))
    except (KeyError, ValueError):
        raise unauthorized()
    if user is None:
        raise unauthorized()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
