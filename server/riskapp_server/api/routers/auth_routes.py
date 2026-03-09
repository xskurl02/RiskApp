"""API router for auth routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from riskapp_server.auth.service import (
    create_access_token,
    hash_pw,
    issue_refresh_token,
    rotate_refresh_token,
    verify_pw,
)
from riskapp_server.core.config import (
    ACCESS_TOKEN_MINUTES,
    LOGIN_RATE_LIMIT_PER_MINUTE,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS,
)
from riskapp_server.core.password_policy import validate_password
from riskapp_server.core.rate_limit import InMemorySlidingWindowLimiter
from riskapp_server.db.session import User, get_db
from riskapp_server.schemas.models import RefreshIn, RegisterIn, TokenOut

router = APIRouter(tags=["auth"])


_login_limiter = InMemorySlidingWindowLimiter(
    limit=LOGIN_RATE_LIMIT_PER_MINUTE, window_s=LOGIN_RATE_LIMIT_WINDOW_SECONDS
)


@router.post("/register", status_code=201, response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Handle register."""
    email = str(payload.email).lower()
    if db.execute(select(User.id).where(User.email == email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    issues = validate_password(payload.password)
    if issues:
        raise HTTPException(status_code=400, detail={"password": issues})

    user = User(email=email, password_hash=hash_pw(payload.password), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_access_token(str(user.id))
    refresh = issue_refresh_token(db, user.id)
    return {
        "user_id": str(user.id),
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": int(ACCESS_TOKEN_MINUTES) * 60,
        "token_type": "bearer",
    }


@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Basic rate limit (per-IP+email). Edge rate limiting is still recommended.
    """Handle login."""
    client_ip = (request.client.host if request.client else "") or "unknown"
    email = form.username.lower()

    allowed, retry_after = _login_limiter.check(f"{client_ip}:{email}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if (
        not user
        or not user.is_active
        or not verify_pw(form.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access = create_access_token(str(user.id))
    refresh = issue_refresh_token(db, user.id)
    return {
        "user_id": str(user.id),
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": int(ACCESS_TOKEN_MINUTES) * 60,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Refresh item."""
    new_refresh, user_id = rotate_refresh_token(db, payload.refresh_token)
    access = create_access_token(str(user_id))
    return {
        "user_id": str(user_id),
        "access_token": access,
        "refresh_token": new_refresh,
        "expires_in": int(ACCESS_TOKEN_MINUTES) * 60,
        "token_type": "bearer",
    }
