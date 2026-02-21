"""SQLite outbox store for offline-first sync.

This module owns ONLY outbox table read/write operations.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from riskapp_client.adapters.local.sqlite_store import LocalStore, utc_iso
from riskapp_client.services.scored_fields import SCORED_ENTITY_OUTBOX_ALLOWED_KEYS


@dataclass(frozen=True)
class PendingChange:
    """A pending change queued for server sync."""
    change_id: str
    entity: str
    op: str
    base_version: Optional[int]
    record: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
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
    def conn(self):
        """Expose sqlite connection for rare advanced usage."""
        return self._store.conn

    def pending_count(self, project_id: Optional[str] = None) -> int:
        if project_id:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE project_id=? AND status='pending';",
                (project_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE status='pending';"
            ).fetchone()
        return int(row["c"]) if row else 0

    def _replace_outbox_entry(
        self,
        *,
        project_id: str,
        entity: str,
        op: str,
        entity_id: str,
        base_version: Optional[int],
        record: Dict[str, Any],
    ) -> str:
        # squash: keep only one pending change per (entity, entity_id)
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM outbox "
            "WHERE project_id=? AND entity=? AND entity_id=? "
            "AND status IN ('pending','blocked');",
            (project_id, entity, entity_id),
        )

        change_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO outbox (
                change_id, project_id, entity, op, entity_id,
                base_version, record_json, status, last_error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', ?)
            """,
            (
                change_id,
                project_id,
                entity,
                op,
                entity_id,
                base_version,
                json.dumps(record),
                utc_iso(),
            ),
        )
        self.conn.commit()
        return change_id

    def queue_risk_upsert(self, project_id: str, record: Dict[str, Any]) -> None:
        """Queue an upsert for a risk record."""
        risk_id = str(record["id"])
        _, ver = self._store.get_risk_project_and_version(risk_id)
        base_v = ver if ver >= 1 else None
        clean = {k: record.get(k) for k in SCORED_ENTITY_OUTBOX_ALLOWED_KEYS if k in record}
        clean["id"] = risk_id
        clean["title"] = str(clean.get("title") or "")
        clean["probability"] = int(clean.get("probability") or 1)
        clean["impact"] = int(clean.get("impact") or 1)

        self._replace_outbox_entry(
            project_id=project_id,
            entity="risk",
            op="upsert",
            entity_id=risk_id,
            base_version=base_v,
            record=clean,
        )

    def queue_opportunity_upsert(self, project_id: str, record: Dict[str, Any]) -> None:
        """Queue an upsert for an opportunity record."""
        opportunity_id = str(record["id"])
        _, ver = self._store.get_opportunity_project_and_version(opportunity_id)
        base_v = ver if ver >= 1 else None
        clean = {k: record.get(k) for k in SCORED_ENTITY_OUTBOX_ALLOWED_KEYS if k in record}
        clean["id"] = opportunity_id
        clean["title"] = str(clean.get("title") or "")
        clean["probability"] = int(clean.get("probability") or 1)
        clean["impact"] = int(clean.get("impact") or 1)

        self._replace_outbox_entry(
            project_id=project_id,
            entity="opportunity",
            op="upsert",
            entity_id=opportunity_id,
            base_version=base_v,
            record=clean,
        )

    def queue_action_upsert(
        self,
        action_id: str,
        project_id: str,
        *,
        risk_id: str | None,
        opportunity_id: str | None,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
    ) -> None:
        """Queue an upsert for an action record."""
        _, ver = self._store.get_action_project_and_version(action_id)
        base_v = ver if ver >= 1 else None

        record_data = {
            "id": action_id,
            "risk_id": risk_id,
            "opportunity_id": opportunity_id,
            "kind": kind,
            "title": title,
            "description": description or None,
            "status": status,
            "owner_user_id": owner_user_id,
        }
        self._replace_outbox_entry(
            project_id=project_id,
            entity="action",
            op="upsert",
            entity_id=action_id,
            base_version=base_v,
            record=record_data,
        )

    def queue_assessment_upsert(
        self,
        assessment_id: str,
        project_id: str,
        risk_id: str,
        assessor_user_id: str,
        probability: int,
        impact: int,
        notes: Optional[str],
    ) -> None:
        """Queue an upsert for an assessment record."""
        _, ver = self._store.get_assessment_project_and_version(assessment_id)
        base_v = ver if ver >= 1 else None

        record_data = {
            "id": assessment_id,
            "risk_id": risk_id,
            "assessor_user_id": assessor_user_id,
            "probability": int(probability),
            "impact": int(impact),
            "notes": notes,
        }
        self._replace_outbox_entry(
            project_id=project_id,
            entity="assessment",
            op="upsert",
            entity_id=assessment_id,
            base_version=base_v,
            record=record_data,
        )

    def get_pending_changes(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT change_id, entity, op, base_version, record_json
            FROM outbox
            WHERE project_id=? AND status='pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (project_id, int(limit)),
        ).fetchall()

        out: List[Dict[str, Any]] = []
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

    def delete_outbox_ids(self, change_ids: List[str]) -> None:
        if not change_ids:
            return
        q = ",".join(["?"] * len(change_ids))
        self.conn.execute(f"DELETE FROM outbox WHERE change_id IN ({q});", change_ids)
        self.conn.commit()

    def block_outbox_id(self, change_id: str, err: str) -> None:
        self.conn.execute(
            "UPDATE outbox SET status='blocked', last_error=? WHERE change_id=?;",
            (err[:500], change_id),
        )
        self.conn.commit()

    def requeue_conflict_with_new_id(self, change_id: str, server_version: int) -> Optional[str]:
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
