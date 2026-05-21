"""JWT authentication — login, refresh, revoke, scope enforcement."""
from datetime import datetime, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.api._limiter import limiter
from app.config import settings

log = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Simple in-memory token revocation set (per-process; fine for single-process dev)
_revoked_tokens: set[str] = set()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _create_token(username: str, scopes: list[str]) -> str:
    payload = {
        "sub": username,
        "scopes": scopes,
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    if token in _revoked_tokens:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return _decode_token(token)


def require_scope(required: str):
    """Dependency factory — raises 403 if token lacks required scope."""
    async def checker(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        scopes = user.get("scopes", [])
        if required not in scopes and "admin" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required}' required",
            )
        return user
    return checker


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, body: LoginRequest):
    if body.username != settings.ADMIN_USERNAME or body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    scopes = ["read", "write", "admin"]
    token = _create_token(body.username, scopes)
    log.info("auth_login", username=body.username)
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def refresh(request: Request, user: Annotated[dict, Depends(get_current_user)]):
    token = _create_token(user["sub"], user.get("scopes", []))
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )


@router.post("/revoke", status_code=204)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def revoke(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    user: Annotated[dict, Depends(get_current_user)],
):
    _revoked_tokens.add(token)
    log.info("auth_revoke", username=user.get("sub"))
