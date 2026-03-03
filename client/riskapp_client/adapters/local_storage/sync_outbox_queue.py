"""SQLite outbox store for offline-first sync.

This module owns ONLY outbox table read/write operations.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore, utc_iso
from riskapp_client.domain.scored_entity_fields import SCORED_ENTITY_OUTBOX_ALLOWED_KEYS

STATUS_PENDING = "pending"
STATUS_BLOCKED = "blocked"


@dataclass(frozen=True)
class PendingChange:
    """A pending change queued for server sync."""

    change_id: str
    entity: str
    op: str
    base_version: int | None
    record: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "entity": self.entity,
            "op": self.op,
            "base_version": self.base_version,
            "record": self.record,
        }


class OutboxStore:
    """Outbox queue for changes to be pushed to the server."""

    def __init__(self, store: LocalStore) -> None:
        self._store = store

    @property
    def conn(self) -> sqlite3.Connection:
        """Expose sqlite connection for rare advanced usage."""
        return self._store.conn

    def pending_count(self, project_id: str | None = None) -> int:
        if project_id:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE project_id=? AND status=?;",
                (project_id, STATUS_PENDING),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE status=?;",
                (STATUS_PENDING,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def blocked_count(self, project_id: str | None = None) -> int:
        """Count changes that are blocked due to sync errors/conflicts."""
        if project_id:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE project_id=? AND status=?;",
                (project_id, STATUS_BLOCKED),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE status=?;",
                (STATUS_BLOCKED,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def _replace_outbox_entry(
        self,
        *,
        project_id: str,
        entity: str,
        op: str,
        entity_id: str,
        base_version: int | None,
        record: dict[str, Any],
    ) -> str:
        # squash: keep only one pending change per (entity, entity_id)
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM outbox "
            "WHERE project_id=? AND entity=? AND entity_id=? "
            "AND status IN (?, ?);",
            (project_id, entity, entity_id, STATUS_PENDING, STATUS_BLOCKED),
        )

        change_id = str(uuid.uuid4())
        # NOTE: use SQL parameters for status values; do not embed placeholders.
        cur.execute(
            """
            INSERT INTO outbox (
                change_id, project_id, entity, op, entity_id,
                base_version, record_json, status, last_error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?)
            """,
            (
                change_id,
                project_id,
                entity,
                op,
                entity_id,
                base_version,
                json.dumps(record),
                STATUS_PENDING,
                utc_iso(),
            ),
        )
        self.conn.commit()
        return change_id

    def override_base_version(
        self,
        project_id: str,
        *,
        entity: str,
        entity_id: str,
        base_version: int | None,
    ) -> None:
        """Override base_version for the current queued change.

        This is mainly useful for conflict rebasing flows where the caller already
        knows the server_version to target and wants to avoid relying on the local
        row version.
        """

        if base_version is None:
            return
        try:
            bv_raw = int(base_version)
        except Exception:
            return
        bv: int | None = bv_raw if bv_raw >= 1 else None

        self.conn.execute(
            "UPDATE outbox SET base_version=? WHERE project_id=? AND entity=? AND entity_id=? AND status IN (?, ?);",
            (bv, project_id, entity, str(entity_id), STATUS_PENDING, STATUS_BLOCKED),
        )
        self.conn.commit()

    def _queue_scored_upsert(
        self,
        project_id: str,
        *,
        entity: str,
        record: dict[str, Any],
        get_project_and_version: Callable[[str], tuple[str, int]],
    ) -> None:
        entity_id = str(record["id"])
        _, ver = get_project_and_version(entity_id)
        base_v = ver if ver >= 1 else None

        clean = {
            k: record.get(k) for k in SCORED_ENTITY_OUTBOX_ALLOWED_KEYS if k in record
        }
        clean["id"] = entity_id
        clean["title"] = str(clean.get("title") or "")
        clean["probability"] = int(clean.get("probability") or 1)
        clean["impact"] = int(clean.get("impact") or 1)

        self._replace_outbox_entry(
            project_id=project_id,
            entity=entity,
            op="upsert",
            entity_id=entity_id,
            base_version=base_v,
            record=clean,
        )

    def _queue_simple_upsert(
        self,
        project_id: str,
        *,
        entity: str,
        entity_id: str,
        record: dict[str, Any],
        get_project_and_version: Callable[[str], tuple[str, int]],
    ) -> None:
        _, ver = get_project_and_version(entity_id)
        base_v = ver if ver >= 1 else None

        self._replace_outbox_entry(
            project_id=project_id,
            entity=entity,
            op="upsert",
            entity_id=entity_id,
            base_version=base_v,
            record=record,
        )

    def queue_risk_upsert(self, project_id: str, record: dict[str, Any]) -> None:
        """Queue an upsert for a risk record."""
        self._queue_scored_upsert(
            project_id,
            entity="risk",
            record=record,
            get_project_and_version=self._store.get_risk_project_and_version,
        )

    def queue_opportunity_upsert(self, project_id: str, record: dict[str, Any]) -> None:
        """Queue an upsert for an opportunity record."""
        self._queue_scored_upsert(
            project_id,
            entity="opportunity",
            record=record,
            get_project_and_version=self._store.get_opportunity_project_and_version,
        )

    def queue_action_upsert(
        self,
        action_id: str,
        project_id: str,
        **kwargs: Any,
    ) -> None:
        """Queue an upsert for an action record."""
        kwargs["id"] = action_id
        self._queue_simple_upsert(
            project_id,
            entity="action",
            entity_id=action_id,
            record=kwargs,
            get_project_and_version=self._store.get_action_project_and_version,
        )

    def queue_assessment_upsert(
        self,
        assessment_id: str,
        project_id: str,
        **kwargs: Any,
    ) -> None:
        """Queue an upsert for an assessment record."""
        kwargs["id"] = assessment_id
        self._queue_simple_upsert(
            project_id,
            entity="assessment",
            entity_id=assessment_id,
            record=kwargs,
            get_project_and_version=self._store.get_assessment_project_and_version,
        )

    def get_pending_changes(
        self, project_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT change_id, entity, op, base_version, record_json
            FROM outbox
            WHERE project_id=? AND status=?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (project_id, STATUS_PENDING, int(limit)),
        ).fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                PendingChange(
                    change_id=row["change_id"],
                    entity=row["entity"],
                    op=row["op"],
                    base_version=row["base_version"],
                    record=json.loads(row["record_json"]),
                ).as_dict()
            )
        return out

    def delete_outbox_ids(self, change_ids: list[str]) -> None:
        if not change_ids:
            return
        q = ",".join(["?"] * len(change_ids))
        self.conn.execute(f"DELETE FROM outbox WHERE change_id IN ({q});", change_ids)
        self.conn.commit()

    def block_outbox_id(self, change_id: str, err: str) -> None:
        self.conn.execute(
            "UPDATE outbox SET status=?, last_error=? WHERE change_id=?;",
            (STATUS_BLOCKED, err[:500], change_id),
        )
        self.conn.commit()

    def requeue_conflict_with_new_id(
        self, change_id: str, server_version: int
    ) -> str | None:
        row = self.conn.execute(
            "SELECT * FROM outbox WHERE change_id=?;", (change_id,)
        ).fetchone()
        if not row:
            return None

        project_id = row["project_id"]
        entity = row["entity"]
        op = row["op"]
        entity_id = row["entity_id"]
        record = json.loads(row["record_json"])

        # Delete old (server stored a receipt for conflict; resending same change_id becomes duplicate)
        self.conn.execute("DELETE FROM outbox WHERE change_id=?;", (change_id,))
        self.conn.commit()

        return self._replace_outbox_entry(
            project_id=project_id,
            entity=entity,
            op=op,
            entity_id=entity_id,
            base_version=int(server_version),
            record=record,
        )
