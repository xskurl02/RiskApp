from __future__ import annotations

import importlib
import os

from fastapi.testclient import TestClient


def _create_isolated_app(db_url: str):
    """Create a server app bound to a unique SQLite DB.

    The server builds its SQLAlchemy engine at import time, so tests that want
    isolated DBs must set env vars and reload modules that captured `get_db`.
    """

    os.environ["DATABASE_URL"] = db_url
    os.environ["AUTO_CREATE_SCHEMA"] = "1"

    import riskapp_server.core.config as cfg

    importlib.reload(cfg)

    import riskapp_server.db.session as session

    importlib.reload(session)

    # Modules that import `get_db` must be reloaded after db.session.
    import riskapp_server.auth.service as auth_service

    importlib.reload(auth_service)

    import riskapp_server.api.routers.crud_factory as crud_factory

    importlib.reload(crud_factory)

    import riskapp_server.api.routers.auth_routes as auth_routes

    importlib.reload(auth_routes)
    import riskapp_server.api.routers.users as users

    importlib.reload(users)
    import riskapp_server.api.routers.projects as projects

    importlib.reload(projects)
    import riskapp_server.api.routers.risks as risks

    importlib.reload(risks)
    import riskapp_server.api.routers.opportunities as opportunities

    importlib.reload(opportunities)
    import riskapp_server.api.routers.items as items

    importlib.reload(items)
    import riskapp_server.api.routers.actions as actions

    importlib.reload(actions)
    import riskapp_server.api.routers.matrix as matrix

    importlib.reload(matrix)
    import riskapp_server.api.routers.snapshots as snapshots

    importlib.reload(snapshots)
    import riskapp_server.api.routers.sync_routes as sync_routes

    importlib.reload(sync_routes)

    import riskapp_server.main.app as main_app

    importlib.reload(main_app)

    return main_app.create_app()


def test_register_create_project_create_items_and_matrix(tmp_path) -> None:
    db_file = tmp_path / "api_smoke.db"
    app = _create_isolated_app(f"sqlite+pysqlite:///{db_file}")

    with TestClient(app) as c:
        # register
        r = c.post(
            "/register",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # create project
        r = c.post(
            "/projects",
            json={"name": "Demo Project", "description": ""},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        project_id = r.json()["id"]

        # create risk
        r = c.post(
            f"/projects/{project_id}/risks",
            json={"type": "risk", "title": "Risk A", "probability": 4, "impact": 3},
            headers=headers,
        )
        assert r.status_code == 201, r.text

        # create opportunity
        r = c.post(
            f"/projects/{project_id}/opportunities",
            json={
                "type": "opportunity",
                "title": "Opp A",
                "probability": 2,
                "impact": 5,
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text

        # matrix must reflect both rows
        r = c.get(f"/projects/{project_id}/matrix?kind=both", headers=headers)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["kind"] == "both"

        # Probability axis is 1..5; impacts are 1..5.
        # risk: (4,3) => risks[3][2] == 1
        assert payload["risks"][3][2] == 1
        # opportunity: (2,5) => opportunities[1][4] == 1
        assert payload["opportunities"][1][4] == 1
