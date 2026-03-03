# RiskApp Desktop Client (PySide6)

This package is the **offline-first desktop client** for the RiskApp project.

## What it does

- Works **offline** using a local SQLite cache + outbox.
- When online, it can **sync** changes to the server and pull updates.
- Provides tabs for:
  - Risks (risk register + qualitative scoring)
  - Opportunities (opportunity register + qualitative scoring)
  - Matrix (probability × impact)
  - Actions (mitigation/contingency/exploit)
  - Assessments (per-user scoring)
  - Members (roles/permissions, online only)
  - Top history (snapshot tracking of top-N items over a period)

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

From the directory **above** `riskapp_client/`:

```bash
# Entry point
python -m riskapp_client.app
```

## First run (create a user)

The desktop client currently assumes the account already exists.
Create a user once via the server:

```bash
curl -X POST http://localhost:8000/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"change-this-password"}'
```

### Configuration (environment variables)

- `RISKAPP_URL` (default: `http://localhost:8000`)
- `RISKAPP_EMAIL` (optional; if missing, a login dialog is shown)
- `RISKAPP_PASSWORD` (optional)
- `RISKAPP_LOCAL_DB` (default: `~/.riskapp/client.sqlite3`)
- `RISKAPP_AUTO_CREATE_PROJECT` (default: `1`)
- `RISKAPP_ALLOW_HTTP` (default: empty)
  - set to `1` only for development if you want to allow `http://` for non-localhost URLs.

## Notes

- The server remains the source of truth for authorization.
- The client uses role checks primarily for UX (enabling/disabling controls).
- The repository should not ship `__pycache__/` or `*.pyc` artifacts.
