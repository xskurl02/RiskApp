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


def pull_since(db: Session, project_id: uuid.UUID, since: datetime) -> dict[str, Any]:
    """Return all entities (including soft-deleted) updated after `since`."""
    risks = db.execute(
        select(Risk).where(Risk.project_id == project_id, Risk.updated_at > since)
    ).scalars().all()

    opportunities = db.execute(
        select(Opportunity).where(
            Opportunity.project_id == project_id, Opportunity.updated_at > since
        )
    ).scalars().all()

    actions = db.execute(
        select(Action).where(
            Action.project_id == project_id, Action.updated_at > since
        )
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
        "risks": risks,
        "opportunities": opportunities,
        "actions": actions,
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
            _store_receipt_best_effort(
                db=db,
                change_id=change_uuid,
                user_id=user_id,
                project_id=project_id,
                entity=str(entity or ""),
                entity_id=None,
                op=str(op or ""),
                status="error",
                response={"reason": "unknown_entity"},
            )
            errors.append(
                {"change_id": str(change_uuid), "reason": "unknown_entity", "entity": entity}
            )
            continue

        if op not in OPS:
            _store_receipt_best_effort(
                db=db,
                change_id=change_uuid,
                user_id=user_id,
                project_id=project_id,
                entity=str(entity),
                entity_id=None,
                op=str(op or ""),
                status="error",
                response={"reason": "unknown_op"},
            )
            errors.append({"change_id": str(change_uuid), "reason": "unknown_op", "op": op})
            continue

        # Permission check (defense-in-depth against clients bypassing normal CRUD endpoints)
        try:
            ensure_role_at_least(role, _min_role_for_change(str(entity), str(op)))
        except HTTPException:
            _store_receipt_best_effort(
                db=db,
                change_id=change_uuid,
                user_id=user_id,
                project_id=project_id,
                entity=str(entity),
                entity_id=_maybe_entity_id(record),
                op=str(op),
                status="error",
                response={"reason": "insufficient_permissions"},
            )
            errors.append(
                {"change_id": str(change_uuid), "entity": entity, "reason": "insufficient_permissions"}
            )
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
            _store_receipt_best_effort(
                db=db,
                change_id=change_uuid,
                user_id=user_id,
                project_id=project_id,
                entity=str(entity),
                entity_id=exc.entity_id,
                op=str(op),
                status="conflict",
                response={"reason": exc.reason, "server_version": exc.server_version},
            )
            conflicts.append(
                {
                    "change_id": str(change_uuid),
                    "entity": entity,
                    "entity_id": str(exc.entity_id) if exc.entity_id else None,
                    "id": str(exc.entity_id) if exc.entity_id else None,
                    "reason": exc.reason,
                    "server_version": exc.server_version,
                }
            )

        except HTTPException as exc:
            _store_receipt_best_effort(
                db=db,
                change_id=change_uuid,
                user_id=user_id,
                project_id=project_id,
                entity=str(entity),
                entity_id=_maybe_entity_id(record),
                op=str(op),
                status="error",
                response={"reason": "http_error", "detail": exc.detail},
            )
            errors.append(
                {
                    "change_id": str(change_uuid),
                    "entity": entity,
                    "reason": "http_error",
                    "detail": exc.detail,
                }
            )

        except Exception as exc:
            _store_receipt_best_effort(
                db=db,
                change_id=change_uuid,
                user_id=user_id,
                project_id=project_id,
                entity=str(entity),
                entity_id=_maybe_entity_id(record),
                op=str(op),
                status="error",
                response={"reason": "exception", "detail": str(exc)},
            )
            errors.append(
                {
                    "change_id": str(change_uuid),
                    "entity": entity,
                    "reason": "exception",
                    "detail": str(exc),
                }
            )

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
    Model = ENTITY_MODELS[entity]

    if entity in {"risk", "opportunity", "action"}:
        obj = (
            db.execute(
                select(Model).where(
                    Model.id == entity_id,
                    Model.project_id == project_id,
                )
            )
            .scalars()
            .first()
        )
    else:
        obj = db.execute(
            select(RiskAssessment).where(RiskAssessment.id == entity_id)
        ).scalars().first()

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
    Model = ENTITY_MODELS[entity]

    if entity in {"risk", "opportunity", "action"}:
        obj = (
            db.execute(
                select(Model).where(
                    Model.id == entity_id,
                    Model.project_id == project_id,
                )
            )
            .scalars()
            .first()
        )
    else:
        obj = db.execute(
            select(RiskAssessment).where(RiskAssessment.id == entity_id)
        ).scalars().first()

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

    if hasattr(obj, "is_deleted"):
        obj.is_deleted = True
    if hasattr(obj, "version"):
        obj.version = int(obj.version) + 1
    if hasattr(obj, "updated_at"):
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

    if entity == "risk":
        p = ensure_int_1_5(record.get("probability", 1), "probability")
        i = overall_impact_from_record(record, 1)
        obj = Risk(
            id=entity_id,
            project_id=project_id,
            title=str(record.get("title") or "").strip() or "Untitled risk",
            probability=p,
            impact=i,
            impact_cost=record.get("impact_cost"),
            impact_time=record.get("impact_time"),
            impact_scope=record.get("impact_scope"),
            impact_quality=record.get("impact_quality"),
            code=(str(record.get("code") or "").strip() or None),
            description=record.get("description"),
            category=(str(record.get("category") or "").strip() or None),
            threat=record.get("threat"),
            triggers=record.get("triggers"),
            mitigation_plan=record.get("mitigation_plan"),
            document_url=record.get("document_url"),
            owner_user_id=parse_uuid(record["owner_user_id"], "owner_user_id")
            if record.get("owner_user_id")
            else None,
            status=(str(record.get("status") or "concept").strip() or "concept"),
            identified_at=parse_dt(record.get("identified_at"), "identified_at") or now,
            status_changed_at=parse_dt(record.get("status_changed_at"), "status_changed_at")
            or now,
            response_at=parse_dt(record.get("response_at"), "response_at"),
            occurred_at=parse_dt(record.get("occurred_at"), "occurred_at"),
            score=compute_score(p, i),
            created_at=parse_dt(record.get("created_at"), "created_at") or now,
            created_by=parse_uuid(record.get("created_by") or user_id, "created_by"),
            updated_at=now,
            version=1,
            is_deleted=bool(record.get("is_deleted") or False),
        )
        db.add(obj)
        return obj

    if entity == "opportunity":
        p = ensure_int_1_5(record.get("probability", 1), "probability")
        i = overall_impact_from_record(record, 1)
        obj = Opportunity(
            id=entity_id,
            project_id=project_id,
            title=str(record.get("title") or "").strip() or "Untitled opportunity",
            probability=p,
            impact=i,
            impact_cost=record.get("impact_cost"),
            impact_time=record.get("impact_time"),
            impact_scope=record.get("impact_scope"),
            impact_quality=record.get("impact_quality"),
            code=(str(record.get("code") or "").strip() or None),
            description=record.get("description"),
            category=(str(record.get("category") or "").strip() or None),
            threat=record.get("threat"),
            triggers=record.get("triggers"),
            mitigation_plan=record.get("mitigation_plan"),
            document_url=record.get("document_url"),
            owner_user_id=parse_uuid(record["owner_user_id"], "owner_user_id")
            if record.get("owner_user_id")
            else None,
            status=(str(record.get("status") or "concept").strip() or "concept"),
            identified_at=parse_dt(record.get("identified_at"), "identified_at") or now,
            status_changed_at=parse_dt(record.get("status_changed_at"), "status_changed_at")
            or now,
            response_at=parse_dt(record.get("response_at"), "response_at"),
            occurred_at=parse_dt(record.get("occurred_at"), "occurred_at"),
            score=compute_score(p, i),
            created_at=parse_dt(record.get("created_at"), "created_at") or now,
            created_by=parse_uuid(record.get("created_by") or user_id, "created_by"),
            updated_at=now,
            version=1,
            is_deleted=bool(record.get("is_deleted") or False),
        )
        db.add(obj)
        return obj

    if entity == "action":
        kind = str(record.get("kind") or "").strip()
        if kind not in ACTION_KIND_ALLOWED:
            raise HTTPException(status_code=400, detail="Invalid action kind")

        risk_uuid = (
            parse_uuid(record["risk_id"], "risk_id") if record.get("risk_id") else None
        )
        opp_uuid = (
            parse_uuid(record["opportunity_id"], "opportunity_id")
            if record.get("opportunity_id")
            else None
        )
        if (risk_uuid is None) == (opp_uuid is None):
            raise HTTPException(
                status_code=400,
                detail="Action must target exactly one of risk_id/opportunity_id",
            )

        obj = Action(
            id=entity_id,
            project_id=project_id,
            risk_id=risk_uuid,
            opportunity_id=opp_uuid,
            kind=kind,
            title=str(record.get("title") or "").strip() or "Untitled action",
            description=record.get("description"),
            status=str(record.get("status") or ActionStatus.open.value).strip()
            or ActionStatus.open.value,
            owner_user_id=parse_uuid(record["owner_user_id"], "owner_user_id")
            if record.get("owner_user_id")
            else None,
            created_by=parse_uuid(record.get("created_by") or user_id, "created_by"),
            created_at=parse_dt(record.get("created_at"), "created_at") or now,
            updated_at=now,
            version=1,
            is_deleted=bool(record.get("is_deleted") or False),
        )

        if obj.status not in ACTION_STATUS_ALLOWED:
            raise HTTPException(status_code=400, detail="Invalid action status")

        db.add(obj)
        return obj

    if entity == "assessment":
        risk_id = parse_uuid(record.get("risk_id"), "risk_id")
        risk = (
            db.execute(select(Risk).where(Risk.id == risk_id, Risk.project_id == project_id))
            .scalars()
            .first()
        )
        if not risk:
            raise HTTPException(status_code=400, detail="risk_id not in project")

        p = ensure_int_1_5(record.get("probability", 1), "probability")
        i = ensure_int_1_5(record.get("impact", 1), "impact")

        obj = RiskAssessment(
            id=entity_id,
            risk_id=risk_id,
            assessor_user_id=parse_uuid(
                record.get("assessor_user_id") or user_id, "assessor_user_id"
            ),
            probability=p,
            impact=i,
            score=compute_score(p, i),
            notes=(record.get("notes") or ""),
            created_at=parse_dt(record.get("created_at"), "created_at") or now,
            updated_at=now,
            version=1,
            is_deleted=bool(record.get("is_deleted") or False),
        )
        db.add(obj)
        return obj

    raise HTTPException(status_code=400, detail="Unsupported entity")


def _update_existing(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    entity: str,
    obj: Any,
    record: dict[str, Any],
) -> None:
    now = utcnow()

    if entity == "risk":
        if "title" in record and record["title"] is not None:
            obj.title = str(record.get("title") or "").strip() or obj.title
        if "probability" in record and record["probability"] is not None:
            obj.probability = ensure_int_1_5(record["probability"], "probability")

        for dim in ("impact_cost", "impact_time", "impact_scope", "impact_quality"):
            if dim in record and record[dim] is not None:
                setattr(obj, dim, ensure_int_1_5(record[dim], dim))
        if "impact" in record and record["impact"] is not None:
            obj.impact = ensure_int_1_5(record["impact"], "impact")

        # metadata
        for field in (
            "code",
            "description",
            "category",
            "threat",
            "triggers",
            "mitigation_plan",
            "document_url",
        ):
            if field in record:
                setattr(obj, field, record.get(field))

        if "owner_user_id" in record:
            obj.owner_user_id = (
                parse_uuid(record["owner_user_id"], "owner_user_id")
                if record.get("owner_user_id")
                else None
            )

        if "status" in record and record["status"] is not None:
            new_status = str(record["status"]).strip()
            if new_status and new_status != obj.status:
                obj.status = new_status
                obj.status_changed_at = now

        for field in ("identified_at", "response_at", "occurred_at"):
            if field in record:
                setattr(obj, field, parse_dt(record.get(field), field))

        obj.impact = overall_impact_from_record(model_to_dict(obj), int(getattr(obj, "impact", 1)))
        obj.score = compute_score(obj.probability, obj.impact)

        obj.updated_at = now
        obj.version = int(obj.version) + 1
        if "is_deleted" in record and record["is_deleted"] is not None:
            obj.is_deleted = bool(record["is_deleted"])
        return

    if entity == "opportunity":
        if "title" in record and record["title"] is not None:
            obj.title = str(record.get("title") or "").strip() or obj.title
        if "probability" in record and record["probability"] is not None:
            obj.probability = ensure_int_1_5(record["probability"], "probability")

        for dim in ("impact_cost", "impact_time", "impact_scope", "impact_quality"):
            if dim in record and record[dim] is not None:
                setattr(obj, dim, ensure_int_1_5(record[dim], dim))
        if "impact" in record and record["impact"] is not None:
            obj.impact = ensure_int_1_5(record["impact"], "impact")

        for field in (
            "code",
            "description",
            "category",
            "threat",
            "triggers",
            "mitigation_plan",
            "document_url",
        ):
            if field in record:
                setattr(obj, field, record.get(field))

        if "owner_user_id" in record:
            obj.owner_user_id = (
                parse_uuid(record["owner_user_id"], "owner_user_id")
                if record.get("owner_user_id")
                else None
            )

        if "status" in record and record["status"] is not None:
            new_status = str(record["status"]).strip()
            if new_status and new_status != obj.status:
                obj.status = new_status
                obj.status_changed_at = now

        for field in ("identified_at", "response_at", "occurred_at"):
            if field in record:
                setattr(obj, field, parse_dt(record.get(field), field))

        obj.impact = overall_impact_from_record(model_to_dict(obj), int(getattr(obj, "impact", 1)))
        obj.score = compute_score(obj.probability, obj.impact)

        obj.updated_at = now
        obj.version = int(obj.version) + 1
        if "is_deleted" in record and record["is_deleted"] is not None:
            obj.is_deleted = bool(record["is_deleted"])
        return

    if entity == "action":
        if "kind" in record and record["kind"] is not None:
            kind = str(record.get("kind") or "").strip()
            if kind not in ACTION_KIND_ALLOWED:
                raise HTTPException(status_code=400, detail="Invalid action kind")
            obj.kind = kind

        for field in ("title", "description"):
            if field in record and record[field] is not None:
                setattr(obj, field, record[field])

        if "status" in record and record["status"] is not None:
            status = str(record["status"]).strip()
            if status not in ACTION_STATUS_ALLOWED:
                raise HTTPException(status_code=400, detail="Invalid action status")
            obj.status = status

        if "owner_user_id" in record:
            obj.owner_user_id = (
                parse_uuid(record["owner_user_id"], "owner_user_id")
                if record.get("owner_user_id")
                else None
            )

        if "risk_id" in record or "opportunity_id" in record:
            risk_uuid = (
                parse_uuid(record["risk_id"], "risk_id") if record.get("risk_id") else None
            )
            opp_uuid = (
                parse_uuid(record["opportunity_id"], "opportunity_id")
                if record.get("opportunity_id")
                else None
            )
            if (risk_uuid is None) == (opp_uuid is None):
                raise HTTPException(
                    status_code=400,
                    detail="Action must target exactly one of risk_id/opportunity_id",
                )
            obj.risk_id = risk_uuid
            obj.opportunity_id = opp_uuid

        obj.updated_at = now
        obj.version = int(obj.version) + 1
        if "is_deleted" in record and record["is_deleted"] is not None:
            obj.is_deleted = bool(record["is_deleted"])
        return

    if entity == "assessment":
        risk = (
            db.execute(select(Risk).where(Risk.id == obj.risk_id, Risk.project_id == project_id))
            .scalars()
            .first()
        )
        if not risk:
            raise HTTPException(
                status_code=400, detail="assessment no longer belongs to project"
            )

        if "probability" in record and record["probability"] is not None:
            obj.probability = ensure_int_1_5(record["probability"], "probability")
        if "impact" in record and record["impact"] is not None:
            obj.impact = ensure_int_1_5(record["impact"], "impact")
        obj.score = compute_score(obj.probability, obj.impact)

        if "notes" in record:
            obj.notes = record.get("notes") or ""

        obj.updated_at = now
        obj.version = int(obj.version) + 1
        if "is_deleted" in record and record["is_deleted"] is not None:
            obj.is_deleted = bool(record["is_deleted"])
        return

    raise HTTPException(status_code=400, detail="Unsupported entity")


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
