"""Sync orchestration for offline-first mode."""

from __future__ import annotations

import json
from typing import Any

from riskapp_client.adapters.local.outbox import OutboxStore
from riskapp_client.adapters.local.sqlite_store import LocalStore, utc_iso


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

    def sync_project(self, project_id: str) -> dict[str, Any]:
        if not self._remote:
            raise RuntimeError("No server configured (start the app online at least once).")

        summary: dict[str, Any] = {
            "pushed": 0,
            "conflicts": 0,
            "errors": 0,
            "pulled_risks": 0,
            "pulled_opportunities": 0,
        }

        changes = self._outbox.get_pending_changes(project_id, limit=100)
        if changes:
            resp = self._remote.sync_push(project_id, changes)
            sent_ids = [c["change_id"] for c in changes]
            conflict_ids = [
                c["change_id"]
                for c in (resp.get("conflicts") or [])
                if c.get("change_id")
            ]
            error_ids = [
                e["change_id"]
                for e in (resp.get("errors") or [])
                if e.get("change_id")
            ]
            dup_ids = list(resp.get("duplicate_change_ids") or [])

            processed = set(sent_ids) - set(conflict_ids) - set(error_ids)
            processed |= set(dup_ids)

            self._outbox.delete_outbox_ids(list(processed))
            summary["pushed"] = len(processed)

            requeued_new_ids: list[str] = []
            for conflict in (resp.get("conflicts") or []):
                cid = str(conflict.get("change_id") or "")
                sv = conflict.get("server_version")
                if cid and sv is not None:
                    new_id = self._outbox.requeue_conflict_with_new_id(cid, int(sv))
                    if new_id:
                        requeued_new_ids.append(new_id)
            summary["conflicts"] = len(requeued_new_ids)

            for err in (resp.get("errors") or []):
                cid = str(err.get("change_id") or "")
                if cid:
                    self._outbox.block_outbox_id(cid, json.dumps(err)[:500])
            summary["errors"] = len(error_ids)

            if requeued_new_ids:
                retry_changes = self._outbox.get_pending_changes(project_id, limit=100)
                retry_set = set(requeued_new_ids)
                retry_changes = [c for c in retry_changes if c["change_id"] in retry_set]

                if retry_changes:
                    resp2 = self._remote.sync_push(project_id, retry_changes)
                    sent2 = [c["change_id"] for c in retry_changes]
                    conflict2 = [
                        c["change_id"]
                        for c in (resp2.get("conflicts") or [])
                        if c.get("change_id")
                    ]
                    error2 = [
                        e["change_id"]
                        for e in (resp2.get("errors") or [])
                        if e.get("change_id")
                    ]
                    dup2 = list(resp2.get("duplicate_change_ids") or [])

                    processed2 = set(sent2) - set(conflict2) - set(error2)
                    processed2 |= set(dup2)
                    self._outbox.delete_outbox_ids(list(processed2))

                    for c in (resp2.get("conflicts") or []):
                        cid = str(c.get("change_id") or "")
                        if cid:
                            self._outbox.block_outbox_id(cid, json.dumps(c)[:500])
                    for e in (resp2.get("errors") or []):
                        cid = str(e.get("change_id") or "")
                        if cid:
                            self._outbox.block_outbox_id(cid, json.dumps(e)[:500])

        since = self._store.get_last_server_time(project_id)
        pull = self._remote.sync_pull(project_id, since)

        assessments = pull.get("assessments") or []
        self._store.apply_pull_assessments(project_id, assessments)
        summary["pulled_assessments"] = len(assessments)

        server_time = str(pull.get("server_time") or utc_iso())

        actions = pull.get("actions") or []
        self._store.apply_pull_actions(project_id, actions)
        summary["pulled_actions"] = len(actions)

        opps = pull.get("opportunities") or []
        self._store.apply_pull_opportunities(project_id, opps)
        summary["pulled_opportunities"] = len(opps)

        risks = pull.get("risks") or []
        self._store.apply_pull_risks(project_id, risks)
        self._store.set_last_server_time(project_id, server_time)
        summary["pulled_risks"] = len(risks)

        return summary
