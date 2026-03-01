"""Sync orchestration for offline-first mode."""

from __future__ import annotations

import json
from typing import Any

from riskapp_client.adapters.local_storage.sync_outbox_queue import OutboxStore
from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore, utc_iso


class SyncService:
    """Push outbox changes, then pull remote changes."""

    def __init__(self, store: LocalStore, outbox: OutboxStore, remote: Any | None) -> None:
        self._store = store
        self._outbox = outbox
        self._remote = remote

    def can_sync(self) -> bool:
        return self._remote is not None

    def pending_count(self, project_id: str | None = None) -> int:
        return self._outbox.pending_count(project_id)

    def _json_snippet(self, obj: object, *, limit: int = 500) -> str:
        """Best-effort short JSON payload for storing in `outbox.last_error`."""
        try:
            return json.dumps(obj)[:limit]
        except Exception:  # noqa: BLE001
            return str(obj)[:limit]

    def _extract_change_ids(self, items: object) -> list[str]:
        """Extract non-empty change_id values from a list of dict-ish objects."""
        out: list[str] = []
        for it in (items or []):
            try:
                cid = str(it.get("change_id") or "")  # type: ignore[union-attr]
            except Exception:
                cid = ""
            if cid:
                out.append(cid)
        return out

    def _push_once(self, project_id: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
        if not self._remote:
            raise RuntimeError("No server configured (start the app online at least once).")
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
        sent_ids = [str(c.get("change_id") or "") for c in changes if c.get("change_id")]

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
        if not self._remote:
            raise RuntimeError("No server configured (start the app online at least once).")

        summary: dict[str, Any] = {
            "pushed": 0,
            "conflicts": 0,
            "errors": 0,
            "pulled_risks": 0,
            "pulled_opportunities": 0,
            "pulled_actions": 0,
            "pulled_assessments": 0,
        }

        changes = self._outbox.get_pending_changes(project_id, limit=100)
        if changes:
            pushed1, conflicts1, errors1 = self._process_push(
                project_id,
                changes,
                block_conflicts=False,
            )
            summary["pushed"] += pushed1
            summary["errors"] += len(self._extract_change_ids(errors1))

            requeued_new_ids = self._requeue_conflicts(conflicts1)
            summary["conflicts"] += len(requeued_new_ids)

            if requeued_new_ids:
                # Retry only the freshly requeued changes once. If they still conflict, block them.
                retry_changes = self._outbox.get_pending_changes(project_id, limit=100)
                retry_set = set(requeued_new_ids)
                retry_changes = [c for c in retry_changes if str(c.get("change_id")) in retry_set]

                if retry_changes:
                    pushed2, _conflicts2, _errors2 = self._process_push(
                        project_id,
                        retry_changes,
                        block_conflicts=True,
                    )
                    summary["pushed"] += pushed2

        since = self._store.get_last_server_time(project_id)
        pull = self._remote.sync_pull(project_id, since)

        server_time = str(pull.get("server_time") or utc_iso())
        for key in ("assessments", "actions", "opportunities", "risks"):
            items = pull.get(key) or []
            getattr(self._store, f"apply_pull_{key}")(project_id, items)
            summary[f"pulled_{key}"] = len(items)

        self._store.set_last_server_time(project_id, server_time)
        return summary
