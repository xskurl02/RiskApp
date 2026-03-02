"""Scheduled retention helper.

This script logs in as an admin user and calls the server's prune endpoint.

Env:
  RISKAPP_BASE_URL           e.g. http://127.0.0.1:8000
  RISKAPP_ADMIN_EMAIL
  RISKAPP_ADMIN_PASSWORD

Usage:
  python -m riskapp_server.ops.prune_job <project_id> [days]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request


def _env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise SystemExit(f"Missing env var: {name}")
    return v


def login(base_url: str, email: str, password: str) -> str:
    data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/login",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return str(payload["access_token"])


def prune(base_url: str, token: str, project_id: str, days: int) -> dict:
    url = (
        base_url.rstrip("/")
        + f"/projects/{project_id}/maintenance/prune?days={int(days)}"
    )
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) not in {2, 3}:
        print(
            "Usage: python -m riskapp_server.ops.prune_job <project_id> [days]",
            file=sys.stderr,
        )
        return 2

    project_id = argv[1]
    days = int(argv[2]) if len(argv) == 3 else int(os.getenv("RETENTION_DAYS", "180"))

    base_url = os.getenv("RISKAPP_BASE_URL", "http://127.0.0.1:8000")
    email = _env("RISKAPP_ADMIN_EMAIL")
    password = _env("RISKAPP_ADMIN_PASSWORD")

    token = login(base_url, email, password)
    res = prune(base_url, token, project_id, days)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
