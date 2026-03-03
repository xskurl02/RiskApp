"""Authentication and security helpers.

- PBKDF2 password hashing (stdlib)
- JWT creation/verification
- `get_current_user` FastAPI dependency
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from riskapp_server.core.config import (
    ACCESS_TOKEN_MINUTES,
    ALGORITHM,
    ALLOW_INSECURE_DEFAULT_SECRET,
    PBKDF2_ITERS,
    REFRESH_TOKEN_DAYS,
    SECRET_KEY,
)
from riskapp_server.db.session import RefreshToken, User, get_db, utcnow

logger = logging.getLogger("riskapp_server.auth")

if SECRET_KEY == "change-me":
    if not ALLOW_INSECURE_DEFAULT_SECRET:
        raise RuntimeError(
            "SECURITY: Set SECRET_KEY env var "
            "(or set ALLOW_INSECURE_DEFAULT_SECRET=1 for local dev)."
        )
    # Keep the service runnable out-of-the-box, but make the risk explicit.
    logger.warning(
        "SECURITY WARNING: Using the default SECRET_KEY. Set SECRET_KEY for any "
        "non-trivial deployment."
    )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def hash_pw(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_pw(password: str, stored_hash: str) -> bool:
    try:
        algo, iters_s, salt_b64, hash_b64 = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iters)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token."""
    exp_dt = utcnow().replace(tzinfo=UTC) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    exp = int(exp_dt.timestamp())
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


# Backward-compatible alias.
create_token = create_access_token


def hash_bearer_secret(raw: str) -> str:
    """Hash refresh/reset tokens for storage.

    We never store raw bearer secrets in the DB. Using HMAC with SECRET_KEY makes
    the stored hash useless if the DB leaks without the server secret.
    """

    return hmac.new(
        SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def issue_refresh_token(db: Session, user_id: uuid.UUID) -> str:
    """Create and persist a refresh token; returns the raw token."""
    raw = secrets.token_urlsafe(48)
    token_hash = hash_bearer_secret(raw)
    expires_at = utcnow() + timedelta(days=int(REFRESH_TOKEN_DAYS))
    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        issued_at=utcnow(),
        expires_at=expires_at,
        revoked_at=None,
        replaced_by_id=None,
    )
    db.add(rt)
    db.commit()
    return raw


def rotate_refresh_token(db: Session, raw_refresh_token: str) -> tuple[str, uuid.UUID]:
    """Validate a refresh token and rotate it.

    Returns:
        (new_refresh_token, user_id)
    """
    now = utcnow()
    token_hash = hash_bearer_secret(raw_refresh_token)
    rt: RefreshToken | None = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .one_or_none()
    )
    if not rt or rt.revoked_at is not None or rt.expires_at <= now:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Rotate (one-time use): revoke the old token, issue a new one.
    rt.revoked_at = now
    new_raw = secrets.token_urlsafe(48)
    new_hash = hash_bearer_secret(new_raw)
    new_rt = RefreshToken(
        user_id=rt.user_id,
        token_hash=new_hash,
        issued_at=now,
        expires_at=now + timedelta(days=int(REFRESH_TOKEN_DAYS)),
        revoked_at=None,
        replaced_by_id=None,
    )
    db.add(new_rt)
    db.flush()  # assign id
    rt.replaced_by_id = new_rt.id
    db.commit()
    return new_raw, rt.user_id


def revoke_user_refresh_tokens(db: Session, user_id: uuid.UUID) -> int:
    """Revoke all active refresh tokens for a user."""
    now = utcnow()
    q = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id)
        .filter(RefreshToken.revoked_at.is_(None))
    )
    count = 0
    for tok in q.all():
        tok.revoked_at = now
        count += 1
    db.commit()
    return count


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise ValueError
        user_id = uuid.UUID(sub)
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
