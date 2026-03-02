"""Application configuration loaded from environment variables.

This module intentionally stays tiny and dependency-free.
"""

from __future__ import annotations

import os


# Environment
#
# "production" enables stricter safety checks (e.g., SECRET_KEY must be set).
ENV: str = os.getenv("ENV", "development").strip().lower()

# Security
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")

# Allow using the default SECRET_KEY in non-production to keep the project
# runnable out-of-the-box. In production you MUST set SECRET_KEY.
ALLOW_INSECURE_DEFAULT_SECRET: bool = (
    os.getenv("ALLOW_INSECURE_DEFAULT_SECRET", "").strip() == "1"
    or ENV != "production"
)
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
TOKEN_MINUTES: int = int(os.getenv("TOKEN_MINUTES", "480"))

# Password hashing (stdlib PBKDF2)
PBKDF2_ITERS: int = int(os.getenv("PBKDF2_ITERS", "200000"))

# Database
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    # Default to SQLite for a zero-dependency local run.
    # Use Postgres in production via DATABASE_URL.
    "sqlite+pysqlite:///./riskapp.db",
)

# Database pool tuning (QueuePool)
DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # seconds; 0 disables
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))

# Postgres statement timeout (milliseconds). 0 disables.
DB_STATEMENT_TIMEOUT_MS: int = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))

# Response compression
GZIP_ENABLED: bool = os.getenv("GZIP_ENABLED", "1").strip() not in {
    "0",
    "false",
    "False",
}
GZIP_MINIMUM_SIZE: int = int(os.getenv("GZIP_MINIMUM_SIZE", "1024"))


# Ops / runtime safety
#
# NOTE: In production, prefer explicit migrations (e.g., Alembic) and set
# AUTO_CREATE_SCHEMA=0.
AUTO_CREATE_SCHEMA: bool = os.getenv("AUTO_CREATE_SCHEMA", "1").strip() not in {
    "0",
    "false",
    "False",
}

# Sync pull: safety cap for the *legacy* non-paginated pull endpoint.
# If exceeded, the server returns HTTP 413 asking the client to paginate.
MAX_SYNC_PULL_PER_ENTITY: int = int(os.getenv("MAX_SYNC_PULL_PER_ENTITY", "5000"))

# Sync push: flush+expunge frequency to avoid growing the ORM identity map.
SYNC_PUSH_EXUNGE_EVERY: int = int(os.getenv("SYNC_PUSH_EXUNGE_EVERY", "200"))

# Snapshot creation: insert chunk size
SNAPSHOT_INSERT_CHUNK: int = int(os.getenv("SNAPSHOT_INSERT_CHUNK", "1000"))

# Maintenance
RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "180"))
