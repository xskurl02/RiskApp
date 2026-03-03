# RiskApp Server (FastAPI)

This package is the **REST API backend** for the RiskApp project (risk + opportunity assessment).

## What it does

- Provides a server-side **risk register** and **opportunity register**.
- Supports **qualitative scoring** (probability 1..5 × impact 1..5).
- Exposes endpoints for:
  - Risks / Opportunities (CRUD)
  - Actions (mitigation / contingency / exploit)
  - Assessments (per-user scoring)
  - Matrix (probability × impact)
  - Top history (snapshot tracking of top-N items over a period)
  - Offline sync (push/pull)
- Implements **authenticated access** (JWT) and role-based access checks.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

From the directory **above** `riskapp_server/`:

```bash
# Development server (auto-creates SQLite DB by default)
uvicorn riskapp_server.main.app:app --reload

# Alternative entry point
python -m riskapp_server
```

## First run (create a user)

The server exposes a simple registration endpoint so you can create your first user.

```bash
curl -X POST http://localhost:8000/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"change-this-password"}'
```

Then log in:

```bash
curl -X POST http://localhost:8000/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@example.com&password=change-this-password'
```

### Configuration (environment variables)

Common settings:

- `DATABASE_URL` (default: `sqlite+pysqlite:///./riskapp.db`)
- `ENV` (default: `development`; set `production` in deployments)
- `SECRET_KEY` (default: `change-me`)
  - **Required in production** unless you explicitly set `ALLOW_INSECURE_DEFAULT_SECRET=1`.
- `ACCESS_TOKEN_MINUTES` (default: `15`)  *(legacy alias: TOKEN_MINUTES)*
- `AUTO_CREATE_SCHEMA` (default: `1`)
  - set to `0` in production if you manage schema with migrations

Sync + safety knobs:

- `MAX_SYNC_PULL_PER_ENTITY` (default: `5000`)
- `SYNC_PUSH_EXUNGE_EVERY` (default: `200`)

## Notes

- Probability and impact are qualitative **1..5**.
- Score is computed as **`probability × impact`**.
- The repository should not ship `__pycache__/` or `*.pyc` artifacts.
