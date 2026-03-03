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
    os.getenv("ALLOW_INSECURE_DEFAULT_SECRET", "").strip() == "1" or ENV != "production"
)
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
TOKEN_MINUTES: int = int(os.getenv("TOKEN_MINUTES", "15"))

# Access tokens should be short-lived; refresh tokens handle longer sessions.
# Backward-compat: ACCESS_TOKEN_MINUTES falls back to TOKEN_MINUTES.
ACCESS_TOKEN_MINUTES: int = int(os.getenv("ACCESS_TOKEN_MINUTES", str(TOKEN_MINUTES)))
REFRESH_TOKEN_DAYS: int = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))

# Basic in-process rate limiting for the /login endpoint (defense-in-depth).
# NOTE: In multi-worker deployments, enforce rate-limits at the edge (NGINX/Envoy)
# or use a shared store (Redis) for consistent limits across workers.
LOGIN_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("LOGIN_RATE_LIMIT_PER_MINUTE", "10"))
LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = int(
    os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60")
)

# Password policy (enforced server-side on register/reset/change).
PASSWORD_MIN_LENGTH: int = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
PASSWORD_MAX_LENGTH: int = int(os.getenv("PASSWORD_MAX_LENGTH", "128"))
PASSWORD_REQUIRE_UPPER: bool = os.getenv("PASSWORD_REQUIRE_UPPER", "1").strip() not in {
    "0",
    "false",
    "False",
}
PASSWORD_REQUIRE_LOWER: bool = os.getenv("PASSWORD_REQUIRE_LOWER", "1").strip() not in {
    "0",
    "false",
    "False",
}
PASSWORD_REQUIRE_DIGIT: bool = os.getenv("PASSWORD_REQUIRE_DIGIT", "1").strip() not in {
    "0",
    "false",
    "False",
}
PASSWORD_REQUIRE_SYMBOL: bool = os.getenv(
    "PASSWORD_REQUIRE_SYMBOL", "1"
).strip() not in {"0", "false", "False"}

PASSWORD_RESET_TOKEN_MINUTES: int = int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "15"))

# For real deployments, password reset tokens must be delivered out-of-band (email/SMS).
# In development/testing, we can return the token in the response for convenience.
PASSWORD_RESET_RETURN_TOKEN: bool = (
    os.getenv("PASSWORD_RESET_RETURN_TOKEN", "").strip() == "1" or ENV != "production"
)

# HTTPS enforcement (best used behind a reverse proxy with TLS termination).
ENFORCE_HTTPS: bool = (
    os.getenv("ENFORCE_HTTPS", "").strip() == "1" or ENV == "production"
)
TRUST_X_FORWARDED_PROTO: bool = os.getenv(
    "TRUST_X_FORWARDED_PROTO", "1" if ENV == "production" else "0"
).strip() not in {"0", "false", "False"}

# Optional bootstrap superuser (created at startup if missing).
INITIAL_SUPERUSER_EMAIL: str | None = os.getenv("INITIAL_SUPERUSER_EMAIL")
INITIAL_SUPERUSER_PASSWORD: str | None = os.getenv("INITIAL_SUPERUSER_PASSWORD")

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
