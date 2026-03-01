"""Authentication and security helpers.

- PBKDF2 password hashing (stdlib)
- JWT creation/verification
- `get_current_user` FastAPI dependency
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import (
    ALGORITHM,
    ALLOW_INSECURE_DEFAULT_SECRET,
    PBKDF2_ITERS,
    SECRET_KEY,
    TOKEN_MINUTES,
)
from core.permissions import require_project_role  # re-exported for compatibility
from db import User, get_db

if SECRET_KEY == "change-me" and not ALLOW_INSECURE_DEFAULT_SECRET:
    raise RuntimeError(
        "SECURITY: Set SECRET_KEY env var "
        "(or set ALLOW_INSECURE_DEFAULT_SECRET=1 for local dev)."
    )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def hash_pw(password: str) -> str:
    """Hash a password using PBKDF2-SHA256."""
    salt = secrets.token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERS
    )
    return "pbkdf2_sha256$%d$%s$%s" % (
        PBKDF2_ITERS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived_key).decode("ascii"),
    )


def verify_pw(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        algo, iters_s, salt_b64, hash_b64 = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iters
        )
        return hmac.compare_digest(derived_key, expected)
    except Exception:
        return False


def create_token(user_id: str) -> str:
    """Create a signed JWT access token."""
    exp = datetime.utcnow() + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """FastAPI dependency returning the authenticated active user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing sub")
        user_id = uuid.UUID(sub)
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user
