from __future__ import annotations

import importlib
import os

from fastapi.testclient import TestClient


def _create_isolated_app(db_url: str):
    os.environ["DATABASE_URL"] = db_url
    os.environ["AUTO_CREATE_SCHEMA"] = "1"

    # Make the limiter deterministic for tests.
    os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "2"
    os.environ["LOGIN_RATE_LIMIT_WINDOW_SECONDS"] = "60"

    import riskapp_server.core.config as cfg

    importlib.reload(cfg)

    import riskapp_server.db.session as session

    importlib.reload(session)

    import riskapp_server.auth.service as auth_service

    importlib.reload(auth_service)

    import riskapp_server.api.routers.crud_factory as crud_factory

    importlib.reload(crud_factory)

    import riskapp_server.api.routers.auth_routes as auth_routes

    importlib.reload(auth_routes)

    import riskapp_server.api.routers.users as users

    importlib.reload(users)

    import riskapp_server.main.app as main_app

    importlib.reload(main_app)
    return main_app.create_app()


def test_password_policy_rejects_weak_password(tmp_path) -> None:
    db_file = tmp_path / "auth_policy.db"
    app = _create_isolated_app(f"sqlite+pysqlite:///{db_file}")
    with TestClient(app) as c:
        r = c.post(
            "/register", json={"email": "x@example.com", "password": "password123"}
        )
        assert r.status_code == 400
        assert "password" in r.json().get("detail", {})


def test_login_rate_limit_kicks_in(tmp_path) -> None:
    db_file = tmp_path / "auth_rate.db"
    app = _create_isolated_app(f"sqlite+pysqlite:///{db_file}")
    with TestClient(app) as c:
        # create user
        r = c.post(
            "/register", json={"email": "u@example.com", "password": "Password123!"}
        )
        assert r.status_code == 201

        # two failed attempts allowed
        for _ in range(2):
            r = c.post(
                "/login",
                data={"username": "u@example.com", "password": "WrongPassword1!"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert r.status_code == 401

        # third attempt within window is blocked
        r = c.post(
            "/login",
            data={"username": "u@example.com", "password": "WrongPassword1!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 429
