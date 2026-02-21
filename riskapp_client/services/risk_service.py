"""Risk write operations for offline-first mode."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from riskapp_client.adapters.local.outbox import OutboxStore
from riskapp_client.adapters.local.sqlite_store import LocalStore, utc_iso
from riskapp_client.domain.models import Risk
from riskapp_client.services.scored_fields import SCORED_ENTITY_META_KEYS

class RiskService:
    """Create/update risks locally and queue sync."""

    def __init__(self, store: LocalStore, outbox: OutboxStore) -> None:
        self._store = store
        self._outbox = outbox

    def list(self, project_id: str) -> list[Risk]:
        return self._store.list_risks(project_id)

    def create(
        self,
        project_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        meta: Mapping[str, Any],
    ) -> Risk:
        risk_id = str(uuid.uuid4())
        now = utc_iso()

        status = (meta.get("status") or "concept")
        identified_at = meta.get("identified_at") or now
        status_changed_at = meta.get("status_changed_at") or now

        record: dict[str, Any] = {
            "id": risk_id,
            "title": title,
            "probability": int(probability),
            "impact": int(impact),
            "status": status,
            "identified_at": identified_at,
            "status_changed_at": status_changed_at,
        }
        for key in SCORED_ENTITY_META_KEYS:
            if key in meta and meta.get(key) is not None:
                record[key] = meta.get(key)

        self._store.upsert_local_risk(
            risk_id=risk_id,
            project_id=project_id,
            title=title,
            probability=int(probability),
            impact=int(impact),
            code=record.get("code"),
            description=record.get("description"),
            category=record.get("category"),
            threat=record.get("threat"),
            triggers=record.get("triggers"),
            mitigation_plan=record.get("mitigation_plan"),
            document_url=record.get("document_url"),
            owner_user_id=record.get("owner_user_id"),
            status=record.get("status"),
            identified_at=record.get("identified_at"),
            status_changed_at=record.get("status_changed_at"),
            response_at=record.get("response_at"),
            occurred_at=record.get("occurred_at"),
            impact_cost=record.get("impact_cost"),
            impact_time=record.get("impact_time"),
            impact_scope=record.get("impact_scope"),
            impact_quality=record.get("impact_quality"),
            version=0,
            is_deleted=False,
            updated_at=utc_iso(),
            dirty=1,
        )
        self._outbox.queue_risk_upsert(project_id, record)
        return Risk(project_id=project_id, version=0, **record)
    
    def update(
        self,
        risk_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        meta: Mapping[str, Any],
    ) -> Risk:
        project_id, version = self._store.get_risk_project_and_version(risk_id)
        now = utc_iso()
        existing = self._store.get_risk_row(risk_id)
        prev_status = (existing["status"] if existing else None) or "concept"
        new_status = meta.get("status") if "status" in meta else prev_status

        status_changed_at = meta.get("status_changed_at")
        if new_status != prev_status and not status_changed_at:
            status_changed_at = now

        record: dict[str, Any] = {
            "id": risk_id,
            "title": title,
            "probability": int(probability),
            "impact": int(impact),
            "status": new_status,
            "status_changed_at": status_changed_at
            if status_changed_at is not None
            else (existing["status_changed_at"] if existing else None),
        }

        def _existing(key: str) -> Any:
            return existing[key] if existing and key in existing.keys() else None

        for key in SCORED_ENTITY_META_KEYS:
            if key in ("status", "status_changed_at"):
                continue
            if key in meta:
                record[key] = meta.get(key)
            else:
                record[key] = _existing(key)

        self._store.upsert_local_risk(
            risk_id=risk_id,
            project_id=project_id,
            title=title,
            probability=int(probability),
            impact=int(impact),
            code=record.get("code"),
            description=record.get("description"),
            category=record.get("category"),
            threat=record.get("threat"),
            triggers=record.get("triggers"),
            mitigation_plan=record.get("mitigation_plan"),
            document_url=record.get("document_url"),
            owner_user_id=record.get("owner_user_id"),
            status=record.get("status"),
            identified_at=record.get("identified_at"),
            status_changed_at=record.get("status_changed_at"),
            response_at=record.get("response_at"),
            occurred_at=record.get("occurred_at"),
            impact_cost=record.get("impact_cost"),
            impact_time=record.get("impact_time"),
            impact_scope=record.get("impact_scope"),
            impact_quality=record.get("impact_quality"),
            version=version,
            is_deleted=False,
            updated_at=utc_iso(),
            dirty=1,
        )
        self._outbox.queue_risk_upsert(project_id, record)
        return Risk(project_id=project_id, version=version, **record)
