from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import case, cast, func, select, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.filters import apply_item_filters
from core.scoring import compute_overall_impact, compute_score
from schemas import ScoreReportOut

def create_item(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, payload, Model):
    now = datetime.utcnow()
    prefix = "R" if Model.__name__ == "Risk" else "O"
    code = (payload.code or f"{prefix}-{uuid.uuid4().hex[:8].upper()}").strip() or None
    
    overall_impact = compute_overall_impact(
        payload.impact,
        impact_cost=payload.impact_cost,
        impact_time=payload.impact_time,
        impact_scope=payload.impact_scope,
        impact_quality=payload.impact_quality,
    )

    item = Model(
        id=uuid.uuid4(),
        project_id=project_id,
        title=payload.title,
        probability=payload.probability,
        impact=overall_impact,
        impact_cost=payload.impact_cost,
        impact_time=payload.impact_time,
        impact_scope=payload.impact_scope,
        impact_quality=payload.impact_quality,
        score=compute_score(payload.probability, overall_impact),
        code=code,
        description=payload.description,
        category=payload.category,
        threat=payload.threat,
        triggers=payload.triggers,
        mitigation_plan=payload.mitigation_plan,
        document_url=payload.document_url,
        owner_user_id=payload.owner_user_id,
        status=(payload.status.value if payload.status else "concept"),
        identified_at=(payload.identified_at or now),
        status_changed_at=now,
        response_at=payload.response_at,
        occurred_at=payload.occurred_at,
        created_at=now,
        created_by=user_id,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"{Model.__name__} code already exists in this project"
        ) from exc
    db.refresh(item)
    return item


def update_item(db: Session, project_id: uuid.UUID, item_id: uuid.UUID, payload, Model):
    now = datetime.utcnow()
    item = db.execute(select(Model).where(Model.project_id == project_id, Model.id == item_id)).scalars().first()
    
    if not item:
        raise HTTPException(status_code=404, detail=f"{Model.__name__} not found")

    if payload.base_version is not None and item.version != payload.base_version:
        raise HTTPException(
            status_code=409, detail={"reason": "version_mismatch", "server_version": item.version}
        )

    # DRY: Use Pydantic's exclude_unset to strictly update only provided fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if field not in ("base_version", "code", "status"):
            setattr(item, field, val)

    if payload.code is not None:
        item.code = payload.code.strip() or None

    if payload.status is not None:
        new_status = payload.status.value
        if new_status != item.status:
            item.status = new_status
            item.status_changed_at = now

    overall_impact = compute_overall_impact(
        int(item.impact),
        impact_cost=getattr(item, "impact_cost", None),
        impact_time=getattr(item, "impact_time", None),
        impact_scope=getattr(item, "impact_scope", None),
        impact_quality=getattr(item, "impact_quality", None),
    )
    item.impact = overall_impact
    item.score = compute_score(item.probability, overall_impact)
    item.updated_at = now
    item.version = int(item.version) + 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"{Model.__name__} code already exists") from exc
    db.refresh(item)
    return item


def list_items(db: Session, project_id: uuid.UUID, Model, filters: dict):
    stmt = select(Model).where(Model.project_id == project_id)
    stmt = apply_item_filters(
        stmt,
        Model,
        search=filters.get("search"),
        min_score=filters.get("min_score"),
        max_score=filters.get("max_score"),
        status=filters.get("status"),
        category=filters.get("category"),
        owner_user_id=filters.get("owner_user_id"),
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date"),
    )
    stmt = stmt.order_by(Model.score.desc(), Model.title.asc())
    return db.execute(stmt).scalars().all()


def delete_item(db: Session, project_id: uuid.UUID, item_id: uuid.UUID, Model):
    item = db.execute(select(Model).where(Model.project_id == project_id, Model.id == item_id)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{Model.__name__} not found")

    item.is_deleted = True
    if hasattr(item, "status") and Model.__name__ != "Action":
        item.status = "deleted"
    if hasattr(item, "status_changed_at"):
        item.status_changed_at = datetime.utcnow()
    item.updated_at = datetime.utcnow()
    item.version = int(item.version) + 1
    db.commit()
    return None


def generate_report(db: Session, project_id: uuid.UUID, Model, filters: dict) -> ScoreReportOut:
    """Generates a comprehensive analytical report for Risks or Opportunities."""
    base_stmt = select(Model).where(Model.project_id == project_id)
    stmt = apply_item_filters(
        base_stmt,
        Model,
        search=filters.get("search"),
        min_score=filters.get("min_score"),
        max_score=filters.get("max_score"),
        status=filters.get("status"),
        category=filters.get("category"),
        owner_user_id=filters.get("owner_user_id"),
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date"),
    )

    # Total in project with the same deleted semantics (but no other filters)
    total_stmt = apply_item_filters(
        select(func.count(Model.id)).where(Model.project_id == project_id),
        Model,
        search=None, min_score=None, max_score=None,
        status=filters.get("status"), category=None,
        owner_user_id=None, from_date=None, to_date=None,
    )
    project_total = int(db.execute(total_stmt).scalar_one() or 0)

    subq = stmt.subquery()
    r = subq.c

    total, mn, mx, avg = db.execute(
        select(func.count(r.id), func.min(r.score), func.max(r.score), func.avg(r.score))
    ).one()

    status_counts = {str(k or "concept"): int(v) for k, v in db.execute(select(r.status, func.count(r.id)).group_by(r.status)).all()}
    category_counts = {str(k): int(v) for k, v in db.execute(select(func.coalesce(r.category, "(none)"), func.count(r.id)).group_by(func.coalesce(r.category, "(none)"))).all()}
    owner_counts = {str(k): int(v) for k, v in db.execute(select(func.coalesce(cast(r.owner_user_id, String), "(none)"), func.count(r.id)).group_by(func.coalesce(cast(r.owner_user_id, String), "(none)"))).all()}

    bucket = case(
        (r.score <= 4, "0-4"),
        (r.score <= 9, "5-9"),
        (r.score <= 14, "10-14"),
        (r.score <= 19, "15-19"),
        else_="20-25",
    )
    score_buckets = {"0-4": 0, "5-9": 0, "10-14": 0, "15-19": 0, "20-25": 0}
    for b, n in db.execute(select(bucket, func.count(r.id)).group_by(bucket)).all():
        score_buckets[str(b)] = int(n or 0)

    return ScoreReportOut(
        total=int(total or 0),
        project_total=project_total,
        min_score=int(mn) if mn is not None else None,
        max_score=int(mx) if mx is not None else None,
        avg_score=float(avg) if avg is not None else None,
        status_counts=status_counts,
        category_counts=category_counts,
        owner_counts=owner_counts,
        score_buckets=score_buckets,
    )
