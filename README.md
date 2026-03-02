# RiskApp (Server + Offline-First Desktop Client)

This repository contains:
- **`riskapp_server/`**: FastAPI backend (JWT auth, RBAC per project, offline sync)
- **`riskapp_client/`**: Qt (PySide6) desktop client with local SQLite + outbox sync

## Quick start (recommended)

### 1) Create a virtualenv

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\\Scripts\\activate
```

### 2) Install dependencies

Server only:
```bash
pip install -r requirements-server.txt
```

Server + client:
```bash
pip install -r requirements-client.txt
```

Or editable install (packaging):
```bash
pip install -e .
# client deps
pip install -e ".[client]"
```

## Run the server

```bash
uvicorn riskapp_server.main:app --reload --host 127.0.0.1 --port 8000
```

Environment variables (optional):
- `DATABASE_URL` (default: `sqlite+pysqlite:///./riskapp.db`)
- `SECRET_KEY` (recommended to set for any real deployment)
- `ENV=production` (enables stricter security expectations)

## Run the client

```bash
# optional (avoids typing credentials every time)
export RISKAPP_URL="http://localhost:8000"
export RISKAPP_EMAIL="you@example.com"
export RISKAPP_PASSWORD="yourpassword"

python -m riskapp_client.app
```

The client will:
- start online if the server is reachable and credentials are valid
- otherwise fall back to offline mode (local cache + outbox)

## Notes

- Authentication endpoints:
  - `POST /register` (JSON: `{email, password}`)
  - `POST /login` (form: `username`, `password`)
- Project membership roles: `viewer < member < manager < admin`
- Offline sync endpoints:
  - `POST /projects/{project_id}/sync/pull`
  - `POST /projects/{project_id}/sync/push`
