from __future__ import annotations

from fastapi import FastAPI

from api.routers.actions import router as actions_router
from api.routers.auth_routes import router as auth_router
from api.routers.matrix import router as matrix_router
from api.routers.opportunities import router as opportunities_router
from api.routers.projects import router as projects_router
from api.routers.risks import router as risks_router
from api.routers.snapshots import router as snapshots_router
from api.routers.sync_routes import router as sync_router
from db import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="Risk / Opportunity API")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(risks_router)
    app.include_router(opportunities_router)
    app.include_router(actions_router)
    app.include_router(matrix_router)
    app.include_router(snapshots_router)
    app.include_router(sync_router)

    return app


app = create_app()
