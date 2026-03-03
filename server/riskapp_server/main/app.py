from __future__ import annotations

import inspect
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from riskapp_server.api.routers.actions import router as actions_router
from riskapp_server.api.routers.auth_routes import router as auth_router
from riskapp_server.api.routers.items import router as items_router
from riskapp_server.api.routers.matrix import router as matrix_router
from riskapp_server.api.routers.projects import router as projects_router
from riskapp_server.api.routers.snapshots import router as snapshots_router
from riskapp_server.api.routers.sync_routes import router as sync_router
from riskapp_server.api.routers.users import router as users_router
from riskapp_server.core.config import (
    GZIP_ENABLED,
    GZIP_MINIMUM_SIZE,
    INITIAL_SUPERUSER_EMAIL,
    INITIAL_SUPERUSER_PASSWORD,
)
from riskapp_server.db.session import engine, init_db
from riskapp_server.main.https_only_middleware import HttpsOnlyMiddleware

logger = logging.getLogger(__name__)

ROUTERS = (
    auth_router,
    users_router,
    projects_router,
    items_router,
    actions_router,
    matrix_router,
    snapshots_router,
    sync_router,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        result = init_db()
        if inspect.isawaitable(result):
            await result

        # Optional: bootstrap a superuser (use env vars; safe for initial setup).
        if INITIAL_SUPERUSER_EMAIL and INITIAL_SUPERUSER_PASSWORD:
            from sqlalchemy import select

            from riskapp_server.auth.service import hash_pw
            from riskapp_server.core.password_policy import validate_password
            from riskapp_server.db.session import SessionLocal, User

            issues = validate_password(INITIAL_SUPERUSER_PASSWORD)
            if issues:
                raise RuntimeError(
                    "INITIAL_SUPERUSER_PASSWORD does not satisfy password policy: "
                    + "; ".join(issues)
                )

            with SessionLocal() as db:
                email = str(INITIAL_SUPERUSER_EMAIL).lower()
                u = (
                    db.execute(select(User).where(User.email == email))
                    .scalars()
                    .first()
                )
                if not u:
                    u = User(
                        email=email,
                        password_hash=hash_pw(INITIAL_SUPERUSER_PASSWORD),
                        is_active=True,
                        is_superuser=True,
                    )
                    db.add(u)
                else:
                    u.is_superuser = True
                    if not u.is_active:
                        u.is_active = True
                db.commit()

        yield
    except Exception:
        logger.exception("Application startup failed")
        raise
    finally:
        # Best-effort cleanup (useful under reload/tests).
        try:
            engine.dispose()
        except Exception:
            logger.exception("DB engine dispose failed")


def create_app() -> FastAPI:
    app = FastAPI(title="Risk / Opportunity API", lifespan=lifespan)
    app.add_middleware(HttpsOnlyMiddleware)
    if GZIP_ENABLED:
        app.add_middleware(GZipMiddleware, minimum_size=GZIP_MINIMUM_SIZE)
    for r in ROUTERS:
        app.include_router(r)
    return app


app = create_app()
