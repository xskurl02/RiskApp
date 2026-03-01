"""Shared offline-first write logic for scored entities (Risk / Opportunity).

Risk and Opportunity share the same local schema and sync shape:
- qualitative dimensions: probability, impact
- shared metadata keys (see `domain.scored_fields`)

Centralizing create/update semantics avoids drift and reduces duplicated code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Type, TypeVar

from riskapp_client.adapters.local_storage.sqlite_data_store import utc_iso
from riskapp_client.domain.scored_entity_fields import SCORED_ENTITY_META_KEYS, DEFAULT_STATUS

ModelT = TypeVar("ModelT")


@dataclass(frozen=True)
class ScoredEntityWiring:
    """Bind entity-specific store/outbox callables."""

    kind: str  # "risk" | "opportunity"
    id_kw: str  # "risk_id" | "opportunity_id"

    model_cls: Type[ModelT]

    list_fn: Callable[[str], list[ModelT]]
    get_project_and_version_fn: Callable[[str], tuple[str, int]]
    get_row_fn: Callable[[str], Mapping[str, Any] | None]

    # Local persistence for the entity.
    upsert_local_fn: Callable[..., None]

    # Outbox queueing for the entity.
    queue_upsert_fn: Callable[[str, dict[str, Any]], None]

    # Optional offline code generator (R-001 / O-001).
    next_code_fn: Callable[[str], str] | None = None


class ScoredEntityService:
    """Create/update scored entities locally and queue sync."""

    def __init__(self, wiring: ScoredEntityWiring) -> None:
        self._w = wiring

    def list(self, project_id: str) -> list[ModelT]:
        return self._w.list_fn(project_id)

    def create(
        self,
        project_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        meta: Mapping[str, Any],
    ) -> ModelT:
        entity_id = str(uuid.uuid4())
        now = utc_iso()

        record: dict[str, Any] = {
            "id": entity_id,
            "title": title,
            "probability": int(probability),
            "impact": int(impact),
            "status": (meta.get("status") or DEFAULT_STATUS),
            "identified_at": meta.get("identified_at") or now,
            "status_changed_at": meta.get("status_changed_at") or now,
        }

        # Copy only explicitly provided meta keys on create (keeps outbox smaller).
        for key in SCORED_ENTITY_META_KEYS:
            if key in record:
                continue
            if key in meta and meta.get(key) is not None:
                record[key] = meta.get(key)

        record["code"] = self._ensure_code(project_id, record.get("code"), existing=None)

        self._upsert_local(project_id=project_id, entity_id=entity_id, record=record, version=0)
        self._w.queue_upsert_fn(project_id, record)
        return self._w.model_cls(project_id=project_id, version=0, **record)

    def update(
        self,
        entity_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        meta: Mapping[str, Any],
    ) -> ModelT:
        project_id, version = self._w.get_project_and_version_fn(entity_id)
        now = utc_iso()

        existing = self._w.get_row_fn(entity_id)
        prev_status = (existing.get("status") if existing else None) or DEFAULT_STATUS
        new_status = meta.get("status") if "status" in meta else prev_status

        status_changed_at = meta.get("status_changed_at")
        if new_status != prev_status and not status_changed_at:
            status_changed_at = now

        record: dict[str, Any] = {
            "id": entity_id,
            "title": title,
            "probability": int(probability),
            "impact": int(impact),
            "status": new_status,
            "status_changed_at": status_changed_at
            if status_changed_at is not None
            else (existing.get("status_changed_at") if existing else None),
        }

        def _existing(key: str) -> Any:
            if not existing:
                return None
            try:
                return existing[key]  # sqlite3.Row
            except Exception:
                return existing.get(key)  # type: ignore[return-value]

        for key in SCORED_ENTITY_META_KEYS:
            if key in ("status", "status_changed_at"):
                continue
            if key in meta:
                record[key] = meta.get(key)
            else:
                record[key] = _existing(key)

        record["code"] = self._ensure_code(project_id, record.get("code"), existing=_existing("code"))

        self._upsert_local(project_id=project_id, entity_id=entity_id, record=record, version=version)
        self._w.queue_upsert_fn(project_id, record)
        return self._w.model_cls(project_id=project_id, version=version, **record)

    def _ensure_code(self, project_id: str, code: Any, *, existing: Any) -> str | None:
        c = None
        if isinstance(code, str):
            c = code.strip() or None
        elif code is not None:
            c = str(code).strip() or None

        if not c:
            if isinstance(existing, str) and existing.strip():
                return existing.strip()
            if self._w.next_code_fn is not None:
                try:
                    return self._w.next_code_fn(project_id)
                except Exception:
                    return None
        return c

    def _upsert_local(self, *, project_id: str, entity_id: str, record: Mapping[str, Any], version: int) -> None:
        kwargs: MutableMapping[str, Any] = {
            self._w.id_kw: entity_id,
            "project_id": project_id,
            "title": str(record.get("title") or ""),
            "probability": int(record.get("probability") or 1),
            "impact": int(record.get("impact") or 1),
            "version": int(version),
            "is_deleted": False,
            "updated_at": utc_iso(),
            "dirty": 1,
        }

        for k in SCORED_ENTITY_META_KEYS:
            kwargs[k] = record.get(k)

        self._w.upsert_local_fn(**kwargs)
