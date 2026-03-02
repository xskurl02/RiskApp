from __future__ import annotations

import uuid
from collections import Counter

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import RiskStatus, utcnow
from ..schemas import ScoreReportOut
from .filters import apply_item_filters
from .scoring import recalculate_item_scores


def create_item(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, payload, Model):
    now = utcnow()
    item_type = getattr(payload, "type", "risk").lower()
    prefix = "R" if item_type == "risk" else "O"
    code = str(payload.code or f"{prefix}-{uuid.uuid4().hex[:8].upper()}").strip()

    data = payload.model_dump(exclude_unset=True)
    data.update(
        {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "code": code,
            "score": 0,
            "status": getattr(payload.status, "value", payload.status)
            or RiskStatus.concept.value,
            "identified_at": payload.identified_at or now,
            "status_changed_at": now,
            "created_at": now,
            "created_by": user_id,
            "updated_at": now,
            "version": 1,
            "is_deleted": False,
        }
    )

    item = Model(**data)
    recalculate_item_scores(item)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Item code already exists in this project"
        ) from exc
    db.refresh(item)
    return item


def update_item(db: Session, project_id: uuid.UUID, item_id: uuid.UUID, payload, Model):
    now = utcnow()
    item = (
        db.execute(
            select(Model).where(Model.project_id == project_id, Model.id == item_id)
        )
        .scalars()
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.base_version is not None and item.version != payload.base_version:
        raise HTTPException(
            status_code=409,
            detail={"reason": "version_mismatch", "server_version": item.version},
        )

    update_data = payload.model_dump(exclude_unset=True, exclude={"base_version"})
    if update_data.get("code"):
        update_data["code"] = str(update_data["code"]).strip()

    for field, val in update_data.items():
        v = getattr(val, "value", val)
        if field == "status":
            item.change_status(v, now)
        else:
            setattr(item, field, v)

    recalculate_item_scores(item)
    item.updated_at = now
    item.version = int(item.version) + 1

    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Item code already exists") from exc

    return item


def list_items(db: Session, project_id: uuid.UUID, Model, filters: dict):
    stmt = (
        apply_item_filters(
            select(Model).where(Model.project_id == project_id),
            Model,
            search=filters.get("search"),
            item_type=filters.get("item_type"),
            min_score=filters.get("min_score"),
            max_score=filters.get("max_score"),
            status=filters.get("status"),
            category=filters.get("category"),
            owner_user_id=filters.get("owner_user_id"),
            from_date=filters.get("from_date"),
            to_date=filters.get("to_date"),
        )
        .order_by(Model.score.desc(), Model.title.asc())
        .limit(filters.get("limit", 100))
        .offset(filters.get("offset", 0))
    )
    return db.execute(stmt).scalars().all()


def delete_item(db: Session, project_id: uuid.UUID, item_id: uuid.UUID, Model):
    item = (
        db.execute(
            select(Model).where(Model.project_id == project_id, Model.id == item_id)
        )
        .scalars()
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.soft_delete(utcnow())
    db.commit()
    return None


def generate_report(
    db: Session, project_id: uuid.UUID, Model, filters: dict
) -> ScoreReportOut:

    project_total = int(
        db.execute(
            apply_item_filters(
                select(func.count(Model.id)).where(Model.project_id == project_id),
                Model,
                search=None,
                item_type=filters.get("item_type"),
                min_score=None,
                max_score=None,
                status=filters.get("status"),
                category=None,
                owner_user_id=None,
                from_date=None,
                to_date=None,
            )
        ).scalar_one()
        or 0
    )

    rows = list_items(db, project_id, Model, filters)
    total = len(rows)
    scores = [r.score for r in rows]
    mn = min(scores) if scores else None
    mx = max(scores) if scores else None
    avg = (sum(scores) / total) if total else None

    status_counts = Counter()
    category_counts = Counter()
    owner_counts = Counter()
    buckets = Counter({"0-4": 0, "5-9": 0, "10-14": 0, "15-19": 0, "20-25": 0})

    for r in rows:
        status_counts[r.status or RiskStatus.concept.value] += 1
        category_counts[r.category or "(none)"] += 1
        owner = str(r.owner_user_id) if r.owner_user_id else "(none)"
        owner_counts[owner] += 1

        # Optimalizace určování rozsahů skóre
        if r.score <= 4:
            b = "0-4"
        elif r.score <= 9:
            b = "5-9"
        elif r.score <= 14:
            b = "10-14"
        elif r.score <= 19:
            b = "15-19"
        else:
            b = "20-25"

        buckets[b] += 1

    return ScoreReportOut(
        total=total,
        project_total=project_total,
        min_score=mn,
        max_score=mx,
        avg_score=avg,
        status_counts=dict(status_counts),
        category_counts=dict(category_counts),
        owner_counts=dict(owner_counts),
        score_buckets=dict(buckets),
    )
