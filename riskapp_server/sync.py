"""Bidirectional sync engine.

This module powers:
- /projects/{project_id}/sync/pull
- /projects/{project_id}/sync/push

Design goals:
- Idempotent push (client-provided change_id)
- Per-change SAVEPOINT to isolate failures
- Optimistic concurrency via base_version
- Soft deletes for sync stability
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.permissions import ensure_role_at_least, require_project_member
from core.scoring import compute_score, ensure_int_1_5, overall_impact_from_record
from db import (
    Action,
    ActionStatus,
    AuditLog,
    Opportunity,
    Risk,
    RiskAssessment,
    SyncReceipt,
)
from schemas import SyncItemRecord, SyncActionRecord, SyncAssessmentRecord

ENTITY_MODELS = {
    "risk": Risk,
    "opportunity": Opportunity,
    "action": Action,
    "assessment": RiskAssessment,
}

OPS = {"upsert", "delete"}

ACTION_KIND_ALLOWED = {"mitigation", "contingency", "exploit"}
ACTION_STATUS_ALLOWED = {
    ActionStatus.open.value,
    ActionStatus.doing.value,
    ActionStatus.done.value,
}


def utcnow() -> datetime:
    return datetime.utcnow()


def parse_dt(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime for {field}") from exc


def parse_uuid(value: Any, field: str) -> uuid.UUID:
    try:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid UUID for {field}") from exc


def model_to_dict(obj: Any) -> dict[str, Any]:
    """Safe-ish serialization for audit logs (JSONB)."""
    data: dict[str, Any] = {}
    for key, value in vars(obj).items():
        if key.startswith("_sa_"):
            continue
        if isinstance(value, uuid.UUID):
            data[key] = str(value)
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        else:
            data[key] = value
    return data


def _min_role_for_change(entity: str, op: str) -> str:
    """Keep aligned with API endpoint permissions."""
    if op == "delete" and entity in {"risk", "opportunity", "action"}:
        return "manager"
    return "member"

def _handle_sync_error(db: Session, errors_list: list, change_id: uuid.UUID, user_id: uuid.UUID, project_id: uuid.UUID, entity: str, entity_id: uuid.UUID | None, op: str, reason: str, detail: str | None = None) -> None:
    """Helper to DRY up error tracking and receipt storage during sync push."""
    resp = {"reason": reason}
    if detail:
        resp["detail"] = detail
        
    _store_receipt_best_effort(
        db=db, change_id=change_id, user_id=user_id, project_id=project_id,
        entity=str(entity or ""), entity_id=entity_id, op=str(op or ""),
        status="error", response=resp
    )
    err_entry = {"change_id": str(change_id), "reason": reason}
    if entity: err_entry["entity"] = entity
    if op: err_entry["op"] = op
    if detail: err_entry["detail"] = detail
    errors_list.append(err_entry)

def _handle_sync_conflict(db: Session, conflicts_list: list, change_id: uuid.UUID, user_id: uuid.UUID, project_id: uuid.UUID, entity: str, entity_id: uuid.UUID | None, op: str, reason: str, server_version: int | None) -> None:
    """Helper to DRY up conflict tracking and receipt storage during sync push."""
    _store_receipt_best_effort(
        db=db, change_id=change_id, user_id=user_id, project_id=project_id,
        entity=str(entity), entity_id=entity_id, op=str(op),
        status="conflict", response={"reason": reason, "server_version": server_version}
    )
    conflicts_list.append({
        "change_id": str(change_id), "entity": entity, "entity_id": str(entity_id) if entity_id else None,
        "id": str(entity_id) if entity_id else None, "reason": reason, "server_version": server_version
    })

def pull_since(db: Session, project_id: uuid.UUID, since: datetime) -> dict[str, Any]:
    """Return all entities (including soft-deleted) updated after `since`."""
    fetched_entities = {}
    for key, Model in [("risks", Risk), ("opportunities", Opportunity), ("actions", Action)]:
        fetched_entities[key] = db.execute(
            select(Model).where(Model.project_id == project_id, Model.updated_at > since)
        ).scalars().all()

    assessments = (
        db.execute(
            select(RiskAssessment)
            .join(Risk, RiskAssessment.risk_id == Risk.id)
            .where(Risk.project_id == project_id, RiskAssessment.updated_at > since)
        )
        .scalars()
        .all()
    )

    return {
        "server_time": utcnow(),
        "risks": fetched_entities["risks"],
        "opportunities": fetched_entities["opportunities"],
        "actions": fetched_entities["actions"],
        "assessments": assessments,
    }


def push_changes(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a batch of client changes with idempotency (change_id via SyncReceipt)."""

    role = require_project_member(db, project_id, user_id)

    accepted = 0
    duplicates = 0
    duplicate_change_ids: list[str] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for change in changes:
        change_id = change.get("change_id")
        entity = change.get("entity")
        op = change.get("op")
        base_version = change.get("base_version")
        record = change.get("record") or {}

        if not change_id:
            errors.append({"reason": "missing_change_id", "change": change})
            continue

        try:
            change_uuid = parse_uuid(change_id, "change_id")
        except HTTPException as exc:
            errors.append(
                {
                    "reason": "invalid_change_id",
                    "detail": exc.detail,
                    "change_id": str(change_id),
                }
            )
            continue

        # Idempotency check
        existing_receipt = (
            db.execute(
                select(SyncReceipt).where(
                    SyncReceipt.change_id == change_uuid,
                    SyncReceipt.project_id == project_id,
                    SyncReceipt.user_id == user_id,
                )
            )
            .scalars()
            .first()
        )
        if existing_receipt:
            duplicates += 1
            duplicate_change_ids.append(str(change_uuid))
            continue

        if entity not in ENTITY_MODELS:
            _handle_sync_error(db, errors, change_uuid, user_id, project_id, entity, None, op, "unknown_entity")            
            continue

        if op not in OPS:
            _handle_sync_error(db, errors, change_uuid, user_id, project_id, entity, None, op, "unknown_op")
            continue

        # Permission check (defense-in-depth against clients bypassing normal CRUD endpoints)
        try:
            ensure_role_at_least(role, _min_role_for_change(str(entity), str(op)))
        except HTTPException:
            _handle_sync_error(db, errors, change_uuid, user_id, project_id, entity, _maybe_entity_id(record), op, "insufficient_permissions")
            continue

        try:
            with db.begin_nested():
                if op == "upsert":
                    entity_id = _apply_upsert(
                        db=db,
                        user_id=user_id,
                        project_id=project_id,
                        entity=str(entity),
                        base_version=base_version,
                        record=record,
                        change_id=change_uuid,
                    )
                else:
                    entity_id = _apply_delete(
                        db=db,
                        user_id=user_id,
                        project_id=project_id,
                        entity=str(entity),
                        base_version=base_version,
                        record=record,
                        change_id=change_uuid,
                    )

                _store_receipt(
                    db,
                    change_id=change_uuid,
                    user_id=user_id,
                    project_id=project_id,
                    entity=str(entity),
                    entity_id=entity_id,
                    op=str(op),
                    status="accepted",
                    response={"entity_id": str(entity_id)},
                )
                db.flush()

            accepted += 1

        except ConflictError as exc:
            _handle_sync_conflict(db, conflicts, change_uuid, user_id, project_id, entity, exc.entity_id, op, exc.reason, exc.server_version)

        except HTTPException as exc:
            _handle_sync_error(db, errors, change_uuid, user_id, project_id, entity, _maybe_entity_id(record), op, "http_error", exc.detail)

        except Exception as exc:
            _handle_sync_error(db, errors, change_uuid, user_id, project_id, entity, _maybe_entity_id(record), op, "exception", str(exc))

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync push commit failed: {exc}")

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "duplicate_change_ids": duplicate_change_ids,
        "conflicts": conflicts,
        "errors": errors,
        "server_time": utcnow(),
    }


def _store_receipt(
    db: Session,
    *,
    change_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    entity_id: uuid.UUID | None,
    op: str,
    status: str,
    response: dict[str, Any],
) -> None:
    db.add(
        SyncReceipt(
            change_id=change_id,
            user_id=user_id,
            project_id=project_id,
            entity=entity,
            entity_id=entity_id,
            op=op,
            status=status,
            response=response or {},
            processed_at=utcnow(),
        )
    )


def _store_receipt_best_effort(**kwargs: Any) -> None:
    """Store a receipt inside a SAVEPOINT, swallowing nothing (raise on DB issues)."""
    db: Session = kwargs["db"]
    with db.begin_nested():
        kwargs.pop("db")
        _store_receipt(db, **kwargs)
        db.flush()


def _maybe_entity_id(record: dict[str, Any]) -> uuid.UUID | None:
    rid = record.get("id")
    if not rid:
        return None
    try:
        return uuid.UUID(str(rid))
    except Exception:
        return None


class ConflictError(Exception):
    def __init__(
        self,
        reason: str,
        entity_id: uuid.UUID | None,
        server_version: int | None,
    ) -> None:
        self.reason = reason
        self.entity_id = entity_id
        self.server_version = server_version
        super().__init__(reason)

def _parse_record(entity: str, record: dict) -> dict:
    """Parses and validates sync records using Pydantic schemas."""
    try:
        if entity in {"risk", "opportunity"}:
            return SyncItemRecord(**record).model_dump(mode='json', exclude_unset=True)
        if entity == "action":
            return SyncActionRecord(**record).model_dump(mode='json', exclude_unset=True)
        if entity == "assessment":
            return SyncAssessmentRecord(**record).model_dump(mode='json', exclude_unset=True)
        return record
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Validation error: {exc}")

def _fetch_obj_for_sync(db: Session, entity: str, entity_id: uuid.UUID, project_id: uuid.UUID):
    Model = ENTITY_MODELS[entity]
    if entity in {"risk", "opportunity", "action"}:
        return db.execute(select(Model).where(Model.id == entity_id, Model.project_id == project_id)).scalars().first()
    else:
        # SECURITY FIX: Ensure the assessment's parent risk actually belongs to the user's project
        return db.execute(
            select(RiskAssessment)
            .join(Risk, RiskAssessment.risk_id == Risk.id)
            .where(RiskAssessment.id == entity_id, Risk.project_id == project_id)
        ).scalars().first()

def _apply_upsert(
    *,
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    base_version: Any,
    record: dict[str, Any],
    change_id: uuid.UUID,
) -> uuid.UUID:
    entity_id = parse_uuid(record.get("id"), "record.id")
    obj = _fetch_obj_for_sync(db, entity, entity_id, project_id)

    if obj is None:
        obj = _create_new(db, user_id, project_id, entity, entity_id, record)
        _audit(
            db=db,
            user_id=user_id,
            project_id=project_id,
            change_id=change_id,
            entity=entity,
            entity_id=entity_id,
            op="upsert",
            before=None,
            after=model_to_dict(obj),
        )
        return entity_id

    if base_version is not None:
        try:
            bv = int(base_version)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="base_version must be int") from exc
        if getattr(obj, "version", None) != bv:
            raise ConflictError("version_mismatch", entity_id, getattr(obj, "version", None))

    before = model_to_dict(obj)
    _update_existing(db, user_id, project_id, entity, obj, record)
    after = model_to_dict(obj)
    _audit(
        db=db,
        user_id=user_id,
        project_id=project_id,
        change_id=change_id,
        entity=entity,
        entity_id=entity_id,
        op="upsert",
        before=before,
        after=after,
    )
    return entity_id


def _apply_delete(
    *,
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    base_version: Any,
    record: dict[str, Any],
    change_id: uuid.UUID,
) -> uuid.UUID:
    entity_id = parse_uuid(record.get("id"), "record.id")
    obj = _fetch_obj_for_sync(db, entity, entity_id, project_id)

    if not obj:
        return entity_id

    if base_version is not None:
        try:
            bv = int(base_version)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="base_version must be int") from exc
        if getattr(obj, "version", None) != bv:
            raise ConflictError("version_mismatch", entity_id, getattr(obj, "version", None))

    before = model_to_dict(obj)

    obj.is_deleted = True
    obj.version = int(obj.version) + 1
    obj.updated_at = utcnow()

    after = model_to_dict(obj)
    _audit(
        db=db,
        user_id=user_id,
        project_id=project_id,
        change_id=change_id,
        entity=entity,
        entity_id=entity_id,
        op="delete",
        before=before,
        after=after,
    )
    return entity_id


def _create_new(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    entity_id: uuid.UUID,
    record: dict[str, Any],
):
    now = utcnow()

    val_data = _parse_record(entity, record)
    Model = ENTITY_MODELS.get(entity)
    if not Model:
        raise HTTPException(status_code=400, detail="Unsupported entity")

    # 1. Provide shared defaults for all new objects
    kwargs = {"id": entity_id, "version": 1, "updated_at": now, "created_at": now}
    if entity != "assessment":
        kwargs.update({"project_id": project_id, "created_by": user_id})

    # 2. Add entity-specific defaults

    if entity in {"risk", "opportunity"}:
        kwargs.update({"title": "Untitled", "probability": 1, "impact": 1})

    elif entity == "action":
        if (val_data.get("risk_id") is None) == (val_data.get("opportunity_id") is None):
            raise HTTPException(status_code=400, detail="Action must target exactly one of risk_id/opportunity_id")
        kwargs.update({"title": "Untitled action", "kind": "mitigation", "status": ActionStatus.open.value})
    elif entity == "assessment":
        if not val_data.get("risk_id"):
            raise HTTPException(status_code=400, detail="risk_id is required")
        kwargs.update({"assessor_user_id": user_id, "probability": 1, "impact": 1})

    # 3. Instantiate model
    obj = Model(**kwargs)
    for k, v in val_data.items():
        if hasattr(obj, k) and k not in {"base_version", "score"}:
            setattr(obj, k, v)


    if entity in {"risk", "opportunity"}:
        obj.impact = overall_impact_from_record(model_to_dict(obj), obj.impact)
        obj.score = compute_score(obj.probability, obj.impact)
    elif entity == "assessment":
        obj.score = compute_score(obj.probability, obj.impact)

    db.add(obj)
    return obj


def _update_existing(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    obj: Any,
    record: dict[str, Any],
) -> None:
    now = utcnow()
    val_data = _parse_record(entity, record)
    if entity == "assessment":
        risk = db.execute(select(Risk).where(Risk.id == obj.risk_id, Risk.project_id == project_id)).scalars().first()
        if not risk:
            raise HTTPException(status_code=400, detail="assessment no longer belongs to project")
    elif entity == "action":
        if "risk_id" in val_data or "opportunity_id" in val_data:
            r_id = val_data.get("risk_id", obj.risk_id)
            o_id = val_data.get("opportunity_id", obj.opportunity_id)
            if (r_id is None) == (o_id is None):
                raise HTTPException(status_code=400, detail="Action must target exactly one")

    for k, v in val_data.items():
        if hasattr(obj, k) and k not in {"base_version", "score"}:
            if k == "status" and entity in {"risk", "opportunity"} and getattr(obj, "status", None) != v:
                obj.status_changed_at = now
            setattr(obj, k, v)

    if entity in {"risk", "opportunity"}:
        obj.impact = overall_impact_from_record(model_to_dict(obj), obj.impact)
        obj.score = compute_score(obj.probability, obj.impact)
    elif entity == "assessment":
        obj.score = compute_score(obj.probability, obj.impact)
    obj.updated_at = now
    obj.version = int(obj.version) + 1
    if "is_deleted" in record and record["is_deleted"] is not None:
        obj.is_deleted = bool(record["is_deleted"])


def _audit(
    *,
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    change_id: uuid.UUID,
    entity: str,
    entity_id: uuid.UUID,
    op: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            project_id=project_id,
            change_id=change_id,
            entity=entity,
            entity_id=entity_id,
            op=op,
            before=before,
            after=after,
            ts=utcnow(),
        )
    )
