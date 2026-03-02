"""Application configuration loaded from environment variables.

This module intentionally stays tiny and dependency-free.
"""

from __future__ import annotations

import os

# Security
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
ALLOW_INSECURE_DEFAULT_SECRET: bool = (
    os.getenv("ALLOW_INSECURE_DEFAULT_SECRET", "").strip() == "1"
)
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
TOKEN_MINUTES: int = int(os.getenv("TOKEN_MINUTES", "480"))

# Password hashing (stdlib PBKDF2)
PBKDF2_ITERS: int = int(os.getenv("PBKDF2_ITERS", "200000"))

# Database
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://riskuser:riskpass@localhost:5432/riskapp",
)
