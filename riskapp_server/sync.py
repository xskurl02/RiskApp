"""Bidirectional offline sync engine."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.action_targets import combine_action_target_ids
from .core.permissions import ensure_member, ensure_role_at_least
from .core.scoring import recalculate_item_scores
from .db import (
    Action,
    ActionStatus,
    AuditLog,
    Opportunity,
    OpportunityAssessment,
    Risk,
    RiskAssessment,
    SyncReceipt,
    utcnow,
)
from .schemas import SyncActionRecord, SyncAssessmentRecord, SyncChange, SyncItemRecord

ENTITY_REGISTRY = {
    "risk": {"model": Risk, "schema": SyncItemRecord, "manager_delete": True, 
             "defaults": {"title": "Untitled", "probability": 1, "impact": 1}},
    "opportunity": {"model": Opportunity, "schema": SyncItemRecord, "manager_delete": True, 
                    "defaults": {"title": "Untitled", "probability": 1, "impact": 1}},
    "action": {"model": Action, "schema": SyncActionRecord, "manager_delete": True, 
               "defaults": {"title": "Untitled action", "kind": "mitigation", "status": ActionStatus.open.value}},
    "assessment": {"model": RiskAssessment, "schema": SyncAssessmentRecord, "manager_delete": False, 
                   "defaults": {"probability": 1, "impact": 1}},
}

ENTITY_MODELS = {k: v["model"] for k, v in ENTITY_REGISTRY.items()}
OPS = {"upsert", "delete"}


def parse_uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid UUID for {field}") from exc


def model_to_dict(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in vars(obj).items():
        if k.startswith("_sa_"):
            continue
        out[k] = str(v) if isinstance(v, uuid.UUID) else v.isoformat() if isinstance(v, datetime) else v
    return out


def _min_role_for_change(entity: str, op: str) -> str:
    return "manager" if op == "delete" and ENTITY_REGISTRY[entity]["manager_delete"] else "member"


def pull_since(db: Session, project_id: uuid.UUID, since: datetime) -> dict[str, Any]:
    out = {}
    for key, Model in (("risks", Risk), ("opportunities", Opportunity), ("actions", Action)):
        out[key] = db.execute(select(Model).where(Model.project_id == project_id, Model.updated_at > since)).scalars().all()

    for key, Model, Parent, fk in (
        ("risk_assessments", RiskAssessment, Risk, RiskAssessment.risk_id),
        ("opportunity_assessments", OpportunityAssessment, Opportunity, OpportunityAssessment.opportunity_id)
    ):
        out[key] = db.execute(
            select(Model).join(Parent, fk == Parent.id).where(Parent.project_id == project_id, Model.updated_at > since)
        ).scalars().all()

    return {"server_time": utcnow(), **out}


class ConflictError(Exception):
    def __init__(self, reason: str, entity_id: uuid.UUID | None, server_version: int | None) -> None:
        super().__init__(reason)
        self.reason, self.entity_id, self.server_version = reason, entity_id, server_version


def push_changes(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, changes: list[SyncChange]) -> dict[str, Any]:
    role = ensure_member(db, project_id, user_id)

    accepted = duplicates = 0
    dup_ids: list[str] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    ids = [c.change_id for c in changes]
    existing = set(
        db.execute(
            select(SyncReceipt.change_id).where(
                SyncReceipt.change_id.in_(ids),
                SyncReceipt.project_id == project_id,
                SyncReceipt.user_id == user_id,
            )
        )
        .scalars()
        .all()
    )

    for ch in changes:
        if ch.change_id in existing:
            duplicates += 1
            dup_ids.append(str(ch.change_id))
            continue

        entity, op, record = (ch.entity or "").strip().lower(), (ch.op or "").strip().lower(), (ch.record or {})
        if entity not in ENTITY_MODELS:
            _receipt_err(db, errors, ch, user_id, project_id, "unknown_entity")
            continue
        if op not in OPS:
            _receipt_err(db, errors, ch, user_id, project_id, "unknown_op")
            continue

        try:
            ensure_role_at_least(role, _min_role_for_change(entity, op))
        except HTTPException:
            _receipt_err(db, errors, ch, user_id, project_id, "insufficient_permissions")
            continue

        try:
            with db.begin_nested():
                eid = (
                    _apply_upsert(db, user_id, project_id, entity, ch.base_version, record, ch.change_id)
                    if op == "upsert"
                    else _apply_delete(db, user_id, project_id, entity, ch.base_version, record, ch.change_id)
                )
                _store_receipt(db, ch.change_id, user_id, project_id, entity, eid, op, "accepted", {"entity_id": str(eid)})
                db.flush()
            accepted += 1

        except ConflictError as exc:
            _store_receipt(db, ch.change_id, user_id, project_id, entity, exc.entity_id, op, "conflict", {"reason": exc.reason, "server_version": exc.server_version})
            conflicts.append({"change_id": str(ch.change_id), "entity": entity, "id": str(exc.entity_id) if exc.entity_id else None, "reason": exc.reason, "server_version": exc.server_version})

        except HTTPException as exc:
            _receipt_err(db, errors, ch, user_id, project_id, "http_error", str(exc.detail))

        except Exception as exc:
            _receipt_err(db, errors, ch, user_id, project_id, "exception", str(exc))

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync push commit failed: {exc}")

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "duplicate_change_ids": dup_ids,
        "conflicts": conflicts,
        "errors": errors,
        "server_time": utcnow(),
    }


def _store_receipt(
    db: Session,
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


def _receipt_err(
    db: Session,
    errors: list[dict[str, Any]],
    ch: SyncChange,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    reason: str,
    detail: str | None = None,
) -> None:
    entity = (ch.entity or "").strip().lower()
    op = (ch.op or "").strip().lower()
    entity_id = _maybe_entity_id(ch.record or {})
    resp: dict[str, Any] = {"reason": reason}
    if detail:
        resp["detail"] = detail

    with db.begin_nested():
        _store_receipt(db, ch.change_id, user_id, project_id, entity, entity_id, op, "error", resp)
        db.flush()

    e = {"change_id": str(ch.change_id), "reason": reason}
    if entity:
        e["entity"] = entity
    if op:
        e["op"] = op
    if detail:
        e["detail"] = detail
    errors.append(e)


def _maybe_entity_id(record: dict[str, Any]) -> uuid.UUID | None:
    rid = record.get("id")
    try:
        return uuid.UUID(str(rid)) if rid else None
    except Exception:
        return None


def _parse_record(entity: str, record: dict) -> dict:
    try:
        Schema = ENTITY_REGISTRY[entity]["schema"]
        return Schema(**record).model_dump(exclude_unset=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Validation error: {exc}")


def _fetch_obj(db: Session, entity: str, entity_id: uuid.UUID, project_id: uuid.UUID):
    Model = ENTITY_MODELS[entity]
    if entity != "assessment":
        return db.execute(select(Model).where(Model.id == entity_id, Model.project_id == project_id)).scalars().first()
    ParentModel = Risk if entity == "risk_assessment" else Opportunity
    parent_field = RiskAssessment.risk_id if entity == "risk_assessment" else OpportunityAssessment.opportunity_id
    return db.execute(select(Model).join(ParentModel, parent_field == ParentModel.id).where(Model.id == entity_id, ParentModel.project_id == project_id)).scalars().first()


def _check_base_version(obj: Any, base_version: Any, entity_id: uuid.UUID) -> None:
    if base_version is None:
        return
    try:
        bv = int(base_version)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="base_version must be int") from exc
    if getattr(obj, "version", None) != bv:
        raise ConflictError("version_mismatch", entity_id, getattr(obj, "version", None))


def _apply_upsert(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    base_version: Any,
    record: dict[str, Any],
    change_id: uuid.UUID,
) -> uuid.UUID:
    entity_id = parse_uuid(record.get("id"), "record.id")
    obj = _fetch_obj(db, entity, entity_id, project_id)

    if obj is None:
        obj = _create_new(db, user_id, project_id, entity, entity_id, record)
        _audit(db, user_id, project_id, change_id, entity, entity_id, "upsert", None, model_to_dict(obj))
        return entity_id

    _check_base_version(obj, base_version, entity_id)
    before = model_to_dict(obj)
    _update_existing(db, user_id, project_id, entity, obj, record)
    _audit(db, user_id, project_id, change_id, entity, entity_id, "upsert", before, model_to_dict(obj))
    return entity_id


def _apply_delete(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    base_version: Any,
    record: dict[str, Any],
    change_id: uuid.UUID,
) -> uuid.UUID:
    entity_id = parse_uuid(record.get("id"), "record.id")
    obj = _fetch_obj(db, entity, entity_id, project_id)
    if not obj:
        return entity_id

    _check_base_version(obj, base_version, entity_id)
    before = model_to_dict(obj)
    obj.soft_delete(utcnow())
    _audit(db, user_id, project_id, change_id, entity, entity_id, "delete", before, model_to_dict(obj))
    return entity_id


def _create_new(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, entity: str, entity_id: uuid.UUID, record: dict[str, Any]):
    now = utcnow()
    val = _parse_record(entity, record)
    Model = ENTITY_MODELS[entity]
    defaults = ENTITY_REGISTRY[entity]["defaults"].copy()
    config = ENTITY_REGISTRY[entity]

    common = {"id": entity_id, "version": 1, "updated_at": now, "created_at": now}
    if entity not in {"risk_assessment", "opportunity_assessment"}:
        common |= {"project_id": project_id, "created_by": user_id}

    # Dynamické načtení výchozích hodnot
    common |= config.get("defaults", {})

    if entity == "action":
        try:
            combine_action_target_ids(risk_id=val.get("risk_id"), opportunity_id=val.get("opportunity_id"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    elif entity in {"risk_assessment", "opportunity_assessment"}:
        parent_field = "risk_id" if entity == "risk_assessment" else "opportunity_id"
        ParentModel = Risk if entity == "risk_assessment" else Opportunity
        
        if not val.get(parent_field):
            raise HTTPException(status_code=400, detail=f"{parent_field} is required")
        if not db.execute(select(ParentModel.id).where(ParentModel.id == val[parent_field], ParentModel.project_id == project_id)).first():
            raise HTTPException(status_code=400, detail=f"{parent_field} not found in project")
        common |= {"assessor_user_id": user_id}
 
    common |= defaults

    obj = Model(**common)

    for k, v in val.items():
        if hasattr(obj, k) and k not in {"score", "assessor_user_id"}:
            setattr(obj, k, getattr(v, "value", v))

    recalculate_item_scores(obj)
    db.add(obj)
    return obj


def _update_existing(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, entity: str, obj: Any, record: dict[str, Any]) -> None:
    now = utcnow()
    val = _parse_record(entity, record)

    if entity in {"risk_assessment", "opportunity_assessment"}:
        parent_field = "risk_id" if entity == "risk_assessment" else "opportunity_id"
        ParentModel = Risk if entity == "risk_assessment" else Opportunity
        parent_id = getattr(obj, parent_field)
        if not db.execute(select(ParentModel.id).where(ParentModel.id == parent_id, ParentModel.project_id == project_id)).first():
            raise HTTPException(status_code=400, detail="assessment no longer belongs to project")

    if entity == "action" and ("risk_id" in val or "opportunity_id" in val):
        r_id = val.get("risk_id", obj.risk_id)
        o_id = val.get("opportunity_id", obj.opportunity_id)
        if (r_id is None) == (o_id is None):
            raise HTTPException(status_code=400, detail="Action must target exactly one")

    for k, v in val.items():
        if hasattr(obj, k) and k not in {"score", "assessor_user_id"}:
            v = getattr(v, "value", v)
            if k == "status" and hasattr(obj, "change_status"):
                obj.change_status(v, now)
            else:
                setattr(obj, k, v)

    recalculate_item_scores(obj)
    obj.updated_at = now
    obj.version = int(getattr(obj, "version", 0)) + 1
    if record.get("is_deleted") is not None:
        obj.is_deleted = bool(record["is_deleted"])

def _audit(
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
