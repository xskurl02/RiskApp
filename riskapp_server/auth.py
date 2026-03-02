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
from datetime import timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .core.config import (
    ALGORITHM,
    ALLOW_INSECURE_DEFAULT_SECRET,
    PBKDF2_ITERS,
    SECRET_KEY,
    TOKEN_MINUTES,
)
from .db import User, get_db, utcnow

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


def create_token(user_id: str) -> str:
    exp = utcnow() + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


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
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user
