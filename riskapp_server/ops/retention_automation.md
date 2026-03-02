# Retention automation

The API exposes an admin-only endpoint:

- `POST /projects/{project_id}/maintenance/prune?days=180`

To automate pruning without an in-app scheduler (recommended for multi-worker deployments),
schedule a periodic HTTP call from outside the application.

## Example: cron (Linux)

1. Create a short-lived admin token (or service account token) and store it securely.
2. Add a cron entry (runs daily at 03:15):

```cron
15 3 * * * /usr/bin/curl -sS -X POST \
  -H 'Authorization: Bearer <ADMIN_TOKEN>' \
  'http://127.0.0.1:8000/projects/<PROJECT_ID>/maintenance/prune?days=180' \
  >/var/log/riskapp_prune.log 2>&1
```

## Example: systemd timer

Create a oneshot service that calls the same curl command, then a timer unit that runs it daily.

## Index migration

Run `riskapp_server/ops/sql/001_add_composite_indexes.sql` once per database.