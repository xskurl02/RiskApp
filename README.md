# RiskApp (Server + Desktop Client)

This repository contains:

- `server/` – FastAPI backend (risk/opportunity register, auth, RBAC, matrix, snapshots, offline sync)
- `client/` – PySide6 desktop client (offline-first SQLite cache + outbox sync)

## Quickstart

### 1) Start the server

```bash
cd server
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

uvicorn riskapp_server.main.app:app --reload
```

Create an initial user:

```bash
curl -X POST http://localhost:8000/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"change-this-password"}'
```

### 2) Start the desktop client

```bash
cd ../client
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python -m riskapp_client.app
```

## Notes

- Offline-first: the client writes to local SQLite first, then syncs via push/pull.
- Roles: `viewer < member < manager < admin`. The server enforces access; the client uses roles mostly for UX.

## QA / Unit tests / Tooling

Developer tooling and unit tests are intentionally kept **outside** both `server/` and `client/`:

- `qa/` – pytest unit tests + black/ruff configs + helper scripts

See `qa/README_QA.md`.
