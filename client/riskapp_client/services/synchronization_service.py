"""Sync orchestration for offline-first mode."""

from __future__ import annotations

import json
from typing import Any

from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore, utc_iso
from riskapp_client.adapters.local_storage.sync_outbox_queue import OutboxStore


class SyncService:
    """Push outbox changes, then pull remote changes."""

    def __init__(
        self, store: LocalStore, outbox: OutboxStore, remote: Any | None
    ) -> None:
        """Internal helper for init."""
        self._store = store
        self._outbox = outbox
        self._remote = remote

    def can_sync(self) -> bool:
        """Return whether sync is allowed."""
        return self._remote is not None

    def pending_count(self, project_id: str | None = None) -> int:
        """Handle pending count."""
        return self._outbox.pending_count(project_id)

    def blocked_count(self, project_id: str | None = None) -> int:
        """Handle blocked count."""
        return self._outbox.blocked_count(project_id)

    def blocked_details(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """Handle blocked details."""
        return self._outbox.get_blocked_changes(project_id)

    def _json_snippet(self, obj: object, *, limit: int = 500) -> str:
        """Best-effort short JSON payload for storing in `outbox.last_error`."""
        try:
            return json.dumps(obj)[:limit]
        except Exception:  # noqa: BLE001
            return str(obj)[:limit]

    def _extract_change_ids(self, items: object) -> list[str]:
        """Extract non-empty change_id values from a list of dict-ish objects."""
        return [
            str(it.get("change_id"))
            for it in (items or [])
            if isinstance(it, dict) and it.get("change_id")
        ]

    def _push_once(
        self, project_id: str, changes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Internal helper for push once."""
        if not self._remote:
            raise RuntimeError(
                "No server configured (start the app online at least once)."
            )
        return self._remote.sync_push(project_id, changes)

    def _process_push(
        self,
        project_id: str,
        changes: list[dict[str, Any]],
        *,
        block_conflicts: bool,
    ) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
        """Push a batch of changes.

        Returns:
            (pushed_count, conflicts_payloads, errors_payloads)
        """
        resp = self._push_once(project_id, changes)
        sent_ids = [
            str(c.get("change_id") or "") for c in changes if c.get("change_id")
        ]

        conflicts = list(resp.get("conflicts") or [])
        errors = list(resp.get("errors") or [])
        dup_ids = [str(x) for x in (resp.get("duplicate_change_ids") or []) if x]

        conflict_ids = set(self._extract_change_ids(conflicts))
        error_ids = set(self._extract_change_ids(errors))

        processed = (set(sent_ids) - conflict_ids - error_ids) | set(dup_ids)
        if processed:
            self._outbox.delete_outbox_ids(list(processed))

        if block_conflicts:
            for c in conflicts:
                cid = str(c.get("change_id") or "")
                if cid:
                    self._outbox.block_outbox_id(cid, self._json_snippet(c))
        for e in errors:
            cid = str(e.get("change_id") or "")
            if cid:
                self._outbox.block_outbox_id(cid, self._json_snippet(e))

        return (len(processed), conflicts, errors)

    def _requeue_conflicts(self, conflicts: list[dict[str, Any]]) -> list[str]:
        """Requeue conflicts as fresh upserts using the latest server_version."""
        new_ids: list[str] = []
        for c in conflicts:
            cid = str(c.get("change_id") or "")
            sv = c.get("server_version")
            if not cid:
                continue
            if sv is None:
                # Without a server version we cannot rebase; block it instead.
                self._outbox.block_outbox_id(cid, self._json_snippet(c))
                continue
            new_id = self._outbox.requeue_conflict_with_new_id(cid, int(sv))
            if new_id:
                new_ids.append(new_id)
        return new_ids

    def sync_project(self, project_id: str) -> dict[str, Any]:
        """Synchronize project."""
        if not self._remote:
            raise RuntimeError(
                "No server configured (start the app online at least once)."
            )

        effective_project_id = project_id

        summary: dict[str, Any] = {
            "pushed": 0,
            "conflicts": 0,
            "errors": 0,
            "blocked": 0,
            "blocked_details": [],
            "pulled_risks": 0,
            "pulled_opportunities": 0,
            "pulled_actions": 0,
            "pulled_assessments": 0,
        }

        # If the user created a project while fully offline, the local project_id
        # won't exist on the server. Promote it to a real server project on the
        # first sync.
        if str(project_id).startswith("local-"):
            promoted = self._promote_local_project(project_id)
            if promoted and promoted != project_id:
                summary["project_id_migrated_from"] = project_id
                summary["project_id_migrated_to"] = promoted
                effective_project_id = promoted

        changes = self._outbox.get_pending_changes(effective_project_id, limit=100)
        if changes:
            pushed1, conflicts1, errors1 = self._process_push(
                effective_project_id,
                changes,
                block_conflicts=False,
            )
            summary["pushed"] += pushed1
            summary["errors"] += len(self._extract_change_ids(errors1))

            requeued_new_ids = self._requeue_conflicts(conflicts1)
            summary["conflicts"] += len(requeued_new_ids)

            if requeued_new_ids:
                # Retry only the freshly requeued changes once. If they still conflict, block them.
                # IMPORTANT: use the effective project id (may differ after local->server promotion).
                retry_changes = self._outbox.get_pending_changes(
                    effective_project_id, limit=100
                )
                retry_set = set(requeued_new_ids)
                retry_changes = [
                    c for c in retry_changes if str(c.get("change_id")) in retry_set
                ]

                if retry_changes:
                    pushed2, _conflicts2, _errors2 = self._process_push(
                        effective_project_id,
                        retry_changes,
                        block_conflicts=True,
                    )
                    summary["pushed"] += pushed2

        since = self._store.get_last_server_time(effective_project_id)

        # Pull (single-shot; if the server requires pagination, fall back to
        # cursor-based pull).
        try:
            pull = self._remote.sync_pull(effective_project_id, since)
        except Exception as exc:  # noqa: BLE001
            status = getattr(exc, "status", None)
            if int(status or 0) != 413:
                raise
            pull = self._pull_paginated(effective_project_id, since)

        server_time = str(pull.get("server_time") or utc_iso())
        for key in ("assessments", "actions", "opportunities", "risks"):
            items = pull.get(key) or []
            getattr(self._store, f"apply_pull_{key}")(effective_project_id, items)
            summary[f"pulled_{key}"] = len(items)

        self._store.set_last_server_time(effective_project_id, server_time)
        summary["blocked_details"] = self.blocked_details(effective_project_id)
        summary["blocked"] = len(summary["blocked_details"])
        return summary

    def _promote_local_project(self, local_project_id: str) -> str | None:
        """Create a server-side project for a local-only project id.

        Returns the new server project id if promotion happened, otherwise None.
        """

        if not self._remote:
            return None

        p = self._store.get_project(local_project_id)
        if not p:
            return None

        # Prefer reusing a single auto-created server project (common first-run case)
        # to avoid leaving behind an empty "MPR Project".
        created = None
        try:
            projects = list(self._remote.list_projects() or [])
        except Exception:
            projects = []

        if len(projects) == 1:
            only = projects[0]
            if (only.name or "").strip() == "MPR Project" or (
                (only.description or "").strip().lower() == "auto-created"
            ):
                created = only

        if created is None and hasattr(self._remote, "create_project"):
            created = self._remote.create_project(
                name=p.name, description=p.description
            )

        if created is None and projects:
            created = projects[0]

        new_id = getattr(created, "id", None) if created else None
        if not new_id:
            return None

        self._store.migrate_project_id(
            old_project_id=local_project_id, new_project_id=str(new_id)
        )
        return str(new_id)

    def _pull_paginated(self, project_id: str, since: str) -> dict[str, Any]:
        """Cursor-based pull to handle large projects.

        The server returns `has_more` + `cursors` only when `limit_per_entity`
        is provided.
        """

        limit = 2000
        cursors: dict[str, str] = {}

        merged: dict[str, Any] = {
            "server_time": None,
            "risks": [],
            "opportunities": [],
            "actions": [],
            "assessments": [],
        }

        while True:
            resp = self._remote.sync_pull(
                project_id,
                since,
                limit_per_entity=limit,
                cursors=cursors or None,
            )
            merged["server_time"] = resp.get("server_time") or merged["server_time"]
            for key in ("risks", "opportunities", "actions", "assessments"):
                merged[key].extend(list(resp.get(key) or []))

            has_more = resp.get("has_more") or {}
            cursors = resp.get("cursors") or {}

            if not any(bool(v) for v in has_more.values()):
                break

        return merged
