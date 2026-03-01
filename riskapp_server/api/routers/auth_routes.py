from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import create_token, hash_pw, verify_pw
from db import User, get_db
from schemas import RegisterIn

router = APIRouter(tags=["auth"])


@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    email_lower = str(payload.email).lower()
    existing = (
        db.execute(select(User).where(User.email == email_lower)).scalars().first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=email_lower, password_hash=hash_pw(payload.password), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(str(user.id))
    return {"user_id": str(user.id), "access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    email_lower = form.username.lower()
    user = db.execute(select(User).where(User.email == email_lower)).scalars().first()
    if not user or not user.is_active or not verify_pw(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = create_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}
