from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routers.actions import router as actions_router
from .api.routers.auth_routes import router as auth_router
from .api.routers.items import router as items_router
from .api.routers.matrix import router as matrix_router
from .api.routers.projects import router as projects_router
from .api.routers.snapshots import router as snapshots_router
from .api.routers.sync_routes import router as sync_router
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Risk / Opportunity API", lifespan=lifespan)
    for r in (
        auth_router,
        projects_router,
        items_router,
        actions_router,
        matrix_router,
        snapshots_router,
        sync_router,
    ):
        app.include_router(r)
    return app


app = create_app()
