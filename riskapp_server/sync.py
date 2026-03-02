"""Bidirectional offline sync engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .core.config import MAX_SYNC_PULL_PER_ENTITY, SYNC_PUSH_EXUNGE_EVERY
from .core.permissions import ensure_member, ensure_role_at_least
from .core.scoring import recalculate_item_scores
from .db import (
    Action,
    ActionStatus,
    Assessment,
    AuditLog,
    Item,
    SyncReceipt,
    utcnow,
)
from .schemas import (
    ActionOut,
    SyncActionRecord,
    SyncAssessmentRecord,
    SyncChange,
    SyncItemRecord,
)

ENTITY_REGISTRY = {
    "risk": {
        "model": Item,
        "schema": SyncItemRecord,
        "manager_delete": True,
        "defaults": {
            "title": "Untitled",
            "probability": 1,
            "impact": 1,
            "type": "risk",
        },
    },
    "opportunity": {
        "model": Item,
        "schema": SyncItemRecord,
        "manager_delete": True,
        "defaults": {
            "title": "Untitled",
            "probability": 1,
            "impact": 1,
            "type": "opportunity",
        },
    },
    "action": {
        "model": Action,
        "schema": SyncActionRecord,
        "manager_delete": True,
        "defaults": {
            "title": "Untitled action",
            "kind": "mitigation",
            "status": ActionStatus.open.value,
        },
    },
    "assessment": {
        "model": Assessment,
        "schema": SyncAssessmentRecord,
        "manager_delete": False,
        "defaults": {"probability": 1, "impact": 1},
        "parent_model": Item,
        "parent_field": "item_id",
    },
}

ENTITY_MODELS = {k: v["model"] for k, v in ENTITY_REGISTRY.items()}
OPS = {"upsert", "delete"}


def parse_uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid UUID for {field}"
        ) from exc


def model_to_dict(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in vars(obj).items():
        if k.startswith("_sa_"):
            continue
        out[k] = (
            str(v)
            if isinstance(v, uuid.UUID)
            else v.isoformat()
            if isinstance(v, datetime)
            else v
        )
    return out


def _min_role_for_change(entity: str, op: str) -> str:
    return (
        "manager"
        if op == "delete" and ENTITY_REGISTRY[entity]["manager_delete"]
        else "member"
    )


def _naive_utc(dt: datetime) -> datetime:
    return (
        dt.astimezone(timezone.utc).replace(tzinfo=None)
        if getattr(dt, "tzinfo", None) is not None
        else dt
    )


def _parse_cursor(
    cur: str | None, *, default_since: datetime
) -> tuple[datetime, uuid.UUID]:
    if not cur:
        return default_since, uuid.UUID(int=0)
    try:
        ts_s, id_s = cur.split("|", 1)
        ts = datetime.fromisoformat(ts_s)
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts, uuid.UUID(id_s)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def _encode_cursor(ts: datetime, entity_id: uuid.UUID) -> str:
    return f"{ts.isoformat()}|{entity_id}"


def pull_since(
    db: Session,
    project_id: uuid.UUID,
    since: datetime,
    *,
    limit_per_entity: int | None = None,
    cursors: dict[str, str] | None = None,
) -> dict[str, Any]:
    # Legacy behavior (no pagination): apply a hard safety cap to prevent
    # unbounded memory/time usage. If exceeded, the client must paginate.
    hard_cap = MAX_SYNC_PULL_PER_ENTITY if limit_per_entity is None else None
    lim = limit_per_entity or hard_cap
    since = _naive_utc(since)
    cursors = cursors or {}

    def item_page(item_type: str, key: str):
        ts, last_id = _parse_cursor(cursors.get(key), default_since=since)
        base_cur = _encode_cursor(ts, last_id)
        q = (
            select(Item)
            .where(
                Item.project_id == project_id,
                Item.type == item_type,
                or_(
                    Item.updated_at > ts, (Item.updated_at == ts) & (Item.id > last_id)
                ),
            )
            .order_by(Item.updated_at.asc(), Item.id.asc())
        )
        rows = db.execute(q.limit(lim + 1) if lim else q).scalars().all()
        more = bool(lim and len(rows) > lim)
        if more:
            rows = rows[:lim]
        next_cur = (
            _encode_cursor(rows[-1].updated_at, rows[-1].id) if rows else base_cur
        )
        return rows, more, next_cur

    risks, more_risks, cur_risks = item_page("risk", "risks")
    opportunities, more_opps, cur_opps = item_page("opportunity", "opportunities")

    # Actions
    ats, alast = _parse_cursor(cursors.get("actions"), default_since=since)
    abase = _encode_cursor(ats, alast)
    aq = (
        select(Action, Item.type)
        .join(Item, Item.id == Action.item_id)
        .where(
            Action.project_id == project_id,
            or_(
                Action.updated_at > ats,
                (Action.updated_at == ats) & (Action.id > alast),
            ),
        )
        .order_by(Action.updated_at.asc(), Action.id.asc())
    )
    action_rows = db.execute(aq.limit(lim + 1) if lim else aq).all()
    more_actions = bool(lim and len(action_rows) > lim)
    if more_actions:
        action_rows = action_rows[:lim]
    actions_out = [
        ActionOut(
            id=a.id,
            project_id=a.project_id,
            risk_id=a.item_id if t == "risk" else None,
            opportunity_id=a.item_id if t == "opportunity" else None,
            kind=a.kind,
            title=a.title,
            description=a.description,
            status=a.status,
            owner_user_id=a.owner_user_id,
            updated_at=a.updated_at,
            version=a.version,
            is_deleted=a.is_deleted,
        ).model_dump()
        for a, t in action_rows
    ]
    cur_actions = (
        _encode_cursor(action_rows[-1][0].updated_at, action_rows[-1][0].id)
        if action_rows
        else abase
    )
    # Assessments (risk-only)
    sts, slast = _parse_cursor(cursors.get("assessments"), default_since=since)
    sbase = _encode_cursor(sts, slast)
    sq = (
        select(Assessment)
        .join(Item, Assessment.item_id == Item.id)
        .where(
            Item.project_id == project_id,
            Item.type == "risk",
            or_(
                Assessment.updated_at > sts,
                (Assessment.updated_at == sts) & (Assessment.id > slast),
            ),
        )
        .order_by(Assessment.updated_at.asc(), Assessment.id.asc())
    )

    assessments = db.execute(sq.limit(lim + 1) if lim else sq).scalars().all()
    more_assessments = bool(lim and len(assessments) > lim)
    if more_assessments:
        assessments = assessments[:lim]
    cur_assessments = (
        _encode_cursor(assessments[-1].updated_at, assessments[-1].id)
        if assessments
        else sbase
    )

    has_more = {
        "risks": more_risks,
        "opportunities": more_opps,
        "actions": more_actions,
        "assessments": more_assessments,
    }
    out = {
        "server_time": utcnow(),
        "risks": risks,
        "opportunities": opportunities,
        "actions": actions_out,
        "assessments": assessments,
    }

    if hard_cap and any(has_more.values()):
        raise HTTPException(
            status_code=413,
            detail=("Sync pull too large. Paginate using limit_per_entity + cursors."),
        )

    if limit_per_entity is not None:
        out["has_more"] = has_more
        out["cursors"] = {
            "risks": cur_risks,
            "opportunities": cur_opps,
            "actions": cur_actions,
            "assessments": cur_assessments,
        }
    return out


class ConflictError(Exception):
    def __init__(
        self, reason: str, entity_id: uuid.UUID | None, server_version: int | None
    ) -> None:
        super().__init__(reason)
        self.reason, self.entity_id, self.server_version = (
            reason,
            entity_id,
            server_version,
        )


def push_changes(
    db: Session, user_id: uuid.UUID, project_id: uuid.UUID, changes: list[SyncChange]
) -> dict[str, Any]:
    role = ensure_member(db, project_id, user_id)

    accepted = duplicates = 0
    dup_ids: list[str] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    wrote = 0

    def _evict_if_needed() -> None:
        nonlocal wrote
        if SYNC_PUSH_EXUNGE_EVERY and wrote and wrote % SYNC_PUSH_EXUNGE_EVERY == 0:
            # Keep the transaction atomic but prevent the session identity map
            # from growing without bounds on large push batches.
            db.flush()
            db.expunge_all()

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

        entity, op, record = (
            (ch.entity or "").strip().lower(),
            (ch.op or "").strip().lower(),
            (ch.record or {}),
        )
        if entity not in ENTITY_MODELS:
            _receipt_err(db, errors, ch, user_id, project_id, "unknown_entity")
            wrote += 1
            _evict_if_needed()
            continue
        if op not in OPS:
            _receipt_err(db, errors, ch, user_id, project_id, "unknown_op")
            wrote += 1
            _evict_if_needed()
            continue

        try:
            ensure_role_at_least(role, _min_role_for_change(entity, op))
        except HTTPException:
            _receipt_err(
                db, errors, ch, user_id, project_id, "insufficient_permissions"
            )
            wrote += 1
            _evict_if_needed()
            continue

        try:
            with db.begin_nested():
                eid = (
                    _apply_upsert(
                        db,
                        user_id,
                        project_id,
                        entity,
                        ch.base_version,
                        record,
                        ch.change_id,
                    )
                    if op == "upsert"
                    else _apply_delete(
                        db,
                        user_id,
                        project_id,
                        entity,
                        ch.base_version,
                        record,
                        ch.change_id,
                    )
                )
                _store_receipt(
                    db,
                    ch.change_id,
                    user_id,
                    project_id,
                    entity,
                    eid,
                    op,
                    "accepted",
                    {"entity_id": str(eid)},
                )
                db.flush()
            accepted += 1
            wrote += 1
            _evict_if_needed()

        except ConflictError as exc:
            _store_receipt(
                db,
                ch.change_id,
                user_id,
                project_id,
                entity,
                exc.entity_id,
                op,
                "conflict",
                {"reason": exc.reason, "server_version": exc.server_version},
            )
            conflicts.append(
                {
                    "change_id": str(ch.change_id),
                    "entity": entity,
                    "id": str(exc.entity_id) if exc.entity_id else None,
                    "reason": exc.reason,
                    "server_version": exc.server_version,
                }
            )
            wrote += 1
            _evict_if_needed()

        except HTTPException as exc:
            _receipt_err(
                db, errors, ch, user_id, project_id, "http_error", str(exc.detail)
            )
            wrote += 1
            _evict_if_needed()

        except Exception as exc:
            _receipt_err(db, errors, ch, user_id, project_id, "exception", str(exc))
            wrote += 1
            _evict_if_needed()

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
        _store_receipt(
            db, ch.change_id, user_id, project_id, entity, entity_id, op, "error", resp
        )
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
        val = Schema(**record).model_dump(exclude_unset=True)
        if entity == "action":
            rid, oid = val.pop("risk_id", None), val.pop("opportunity_id", None)
            if not val.get("item_id"):
                if bool(rid) == bool(oid):
                    raise HTTPException(
                        status_code=400,
                        detail="Action must have exactly one of risk_id/opportunity_id",
                    )
                val["item_id"], val["_target_type"] = (
                    rid or oid,
                    "risk" if rid else "opportunity",
                )
        elif entity == "assessment":
            rid = val.pop("risk_id", None)
            if not val.get("item_id") and rid:
                val["item_id"] = rid
            val["_target_type"] = "risk"
        return val
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Validation error: {exc}")


def _ensure_item_in_project(
    db: Session,
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    expected_type: str | None = None,
) -> None:
    t = db.execute(
        select(Item.type).where(
            Item.project_id == project_id,
            Item.id == item_id,
        )
    ).scalar()
    if not t or (expected_type and t != expected_type):
        raise HTTPException(status_code=400, detail="Target not found in project")


def _fetch_obj(db: Session, entity: str, entity_id: uuid.UUID, project_id: uuid.UUID):
    Model = ENTITY_MODELS[entity]
    config = ENTITY_REGISTRY[entity]
    if "parent_model" not in config:
        return (
            db.execute(
                select(Model).where(
                    Model.id == entity_id, Model.project_id == project_id
                )
            )
            .scalars()
            .first()
        )
    ParentModel = config["parent_model"]
    return (
        db.execute(
            select(Assessment)
            .join(Item, Assessment.item_id == Item.id)
            .where(Assessment.id == entity_id, Item.project_id == project_id)
        )
        .scalars()
        .first()
    )


def _check_base_version(obj: Any, base_version: Any, entity_id: uuid.UUID) -> None:
    if base_version is None:
        return
    try:
        bv = int(base_version)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="base_version must be int") from exc
    if getattr(obj, "version", None) != bv:
        raise ConflictError(
            "version_mismatch", entity_id, getattr(obj, "version", None)
        )


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

    if (
        obj is not None
        and entity in {"risk", "opportunity"}
        and getattr(obj, "type", None) != entity
    ):
        raise ConflictError("type_mismatch", entity_id, getattr(obj, "version", None))

    if obj is None:
        obj = _create_new(db, user_id, project_id, entity, entity_id, record)
        _audit(
            db,
            user_id,
            project_id,
            change_id,
            entity,
            entity_id,
            "upsert",
            None,
            model_to_dict(obj),
        )
        return entity_id

    if entity == "assessment" and getattr(obj, "assessor_user_id", None) != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot modify another user's assessment"
        )

    _check_base_version(obj, base_version, entity_id)
    before = model_to_dict(obj)
    _update_existing(db, user_id, project_id, entity, obj, record)
    _audit(
        db,
        user_id,
        project_id,
        change_id,
        entity,
        entity_id,
        "upsert",
        before,
        model_to_dict(obj),
    )
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

    if entity == "assessment" and getattr(obj, "assessor_user_id", None) != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot modify another user's assessment"
        )

    if entity in {"risk", "opportunity"} and getattr(obj, "type", None) != entity:
        raise ConflictError("type_mismatch", entity_id, getattr(obj, "version", None))

    _check_base_version(obj, base_version, entity_id)
    before = model_to_dict(obj)
    obj.soft_delete(utcnow())
    _audit(
        db,
        user_id,
        project_id,
        change_id,
        entity,
        entity_id,
        "delete",
        before,
        model_to_dict(obj),
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
    val = _parse_record(entity, record)
    Model = ENTITY_MODELS[entity]
    defaults = ENTITY_REGISTRY[entity]["defaults"].copy()
    config = ENTITY_REGISTRY[entity]

    common = {"id": entity_id, "version": 1, "updated_at": now, "created_at": now}
    if entity != "assessment":
        common |= {"project_id": project_id, "created_by": user_id}

    # Dynamické načtení výchozích hodnot
    common |= config.get("defaults", {})

    if "parent_model" in config:
        parent_field = config["parent_field"]
        if not val.get(parent_field):
            raise HTTPException(status_code=400, detail=f"{parent_field} is required")
        _ensure_item_in_project(
            db,
            project_id,
            parse_uuid(val[parent_field], parent_field),
            expected_type=val.get("_target_type"),
        )
        common |= {
            "assessor_user_id": user_id
        }  # Pro budoucí rozšíření zvážit přesun do config

    if entity == "action" and val.get("item_id"):
        _ensure_item_in_project(
            db,
            project_id,
            parse_uuid(val["item_id"], "item_id"),
            expected_type=val.get("_target_type"),
        )

    common |= defaults

    obj = Model(**common)

    for k, v in val.items():
        if hasattr(obj, k) and k not in {"score", "assessor_user_id"}:
            setattr(obj, k, getattr(v, "value", v))

    recalculate_item_scores(obj)
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
    val = _parse_record(entity, record)
    config = ENTITY_REGISTRY[entity]

    if "parent_model" in config:
        parent_field = config["parent_field"]
        # Validate the (possibly updated) parent reference to prevent cross-project
        # reassociation (important for assessments).
        target_parent = val.get(parent_field) or getattr(obj, parent_field)
        _ensure_item_in_project(
            db,
            project_id,
            parse_uuid(target_parent, parent_field),
            expected_type=val.get("_target_type"),
        )

    if entity == "action" and val.get("item_id"):
        _ensure_item_in_project(
            db,
            project_id,
            parse_uuid(val["item_id"], "item_id"),
            expected_type=val.get("_target_type"),
        )

    for k, v in val.items():
        if hasattr(obj, k) and k not in {"score", "assessor_user_id"}:
            v = getattr(v, "value", v)
            if k == "status" and hasattr(obj, "change_status"):
                obj.change_status(v, now)
            else:
                setattr(obj, k, v)

    if record.get("is_deleted") is not None:
        if record["is_deleted"]:
            obj.soft_delete(now)
        else:
            obj.is_deleted = False

    recalculate_item_scores(obj)
    obj.updated_at = now
    obj.version = int(getattr(obj, "version", 0)) + 1


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
