"""API router for users."""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from riskapp_server.auth.service import (
    get_current_user,
    hash_bearer_secret,
    hash_pw,
    revoke_user_refresh_tokens,
    verify_pw,
)
from riskapp_server.core.config import (
    PASSWORD_RESET_RETURN_TOKEN,
    PASSWORD_RESET_TOKEN_MINUTES,
)
from riskapp_server.core.password_policy import validate_password
from riskapp_server.db.session import PasswordResetToken, User, get_db, utcnow
from riskapp_server.schemas.models import (
    AdminSetPasswordIn,
    ChangePasswordIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    UserOut,
)

router = APIRouter(tags=["users"])


def _require_superuser(user: User) -> None:
    """Internal helper for require superuser."""
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")


def _apply_new_password(db: Session, user: User, new_password: str) -> None:
    """Internal helper for apply new password."""
    issues = validate_password(new_password)
    if issues:
        raise HTTPException(status_code=400, detail={"password": issues})
    user.password_hash = hash_pw(new_password)
    revoke_user_refresh_tokens(db, user.id)
    db.add(user)
    db.commit()


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Handle me."""
    return user


@router.post("/users/me/change-password", status_code=204)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Handle change password."""
    if not verify_pw(payload.old_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid current password")
    _apply_new_password(db, user, payload.new_password)
    return None


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    # Enumeration-safe: response does not reveal whether the account exists.
    """Handle request password reset."""
    email = str(payload.email).lower()
    user = db.execute(select(User).where(User.email == email)).scalars().first()

    token_raw: str | None = None
    if user and user.is_active:
        token_raw = secrets.token_urlsafe(48)
        pr = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_bearer_secret(token_raw),
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(minutes=int(PASSWORD_RESET_TOKEN_MINUTES)),
            used_at=None,
            request_ip=(request.client.host if request.client else None),
        )
        db.add(pr)
        db.commit()

    # In production you'd email the token to the user.
    # For local dev/testing, optionally return it.
    if token_raw and PASSWORD_RESET_RETURN_TOKEN:
        return {"detail": "Password reset token created", "token": token_raw}
    return {"detail": "If the account exists, reset instructions were issued."}


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(
    payload: PasswordResetConfirmIn, db: Session = Depends(get_db)
):
    """Handle confirm password reset."""
    now = utcnow()
    token_hash = hash_bearer_secret(payload.token)
    pr: PasswordResetToken | None = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .one_or_none()
    )
    if not pr or pr.used_at is not None or pr.expires_at <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.get(User, pr.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")

    _apply_new_password(db, user, payload.new_password)
    pr.used_at = now
    db.add(pr)
    db.commit()
    return None


@router.post("/admin/users/{user_id}/deactivate", status_code=204)
def admin_deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Handle admin deactivate user."""
    _require_superuser(actor)
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    target.deactivated_at = utcnow()
    db.add(target)
    db.commit()
    revoke_user_refresh_tokens(db, target.id)
    return None


@router.post("/admin/users/{user_id}/activate", status_code=204)
def admin_activate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Handle admin activate user."""
    _require_superuser(actor)
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = True
    target.deactivated_at = None
    db.add(target)
    db.commit()
    return None


@router.post("/admin/users/{user_id}/set-password", status_code=204)
def admin_set_password(
    user_id: uuid.UUID,
    payload: AdminSetPasswordIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Handle admin set password."""
    _require_superuser(actor)
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    _apply_new_password(db, target, payload.new_password)
    return None
