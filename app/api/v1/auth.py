from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.auth import (
    AuthSession,
    AuthTokens,
    AuthUser,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services.auth_service import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidRefreshError,
    build_user,
    login_user,
    logout_user,
    refresh_session,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthSession, status_code=201)
def register(body: RegisterRequest, db: SessionDep) -> AuthSession:
    try:
        return register_user(db, body.name, body.email, body.password)
    except EmailTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )


@router.post("/login", response_model=AuthSession)
def login(body: LoginRequest, db: SessionDep) -> AuthSession:
    try:
        return login_user(db, body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )


@router.post("/refresh", response_model=AuthTokens)
def refresh(body: RefreshRequest, db: SessionDep) -> AuthTokens:
    try:
        return refresh_session(db, body.refresh_token)
    except InvalidRefreshError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid refresh token",
        )


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: SessionDep) -> Response:
    logout_user(db, body.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=AuthUser)
def me(user: CurrentUserDep) -> AuthUser:
    return build_user(user)
