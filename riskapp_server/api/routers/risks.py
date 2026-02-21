from __future__ import annotations

import uuid
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from core.filters import apply_item_filters
from core.permissions import ensure_member, require_min_role
from core.scoring import compute_overall_impact, compute_score
from db import Risk, RiskAssessment, User, get_db
from schemas import (
    RiskAssessmentIn,
    RiskAssessmentOut,
    RiskCreate,
    RiskOut,
    RiskUpdate,
    ScoreReportOut,
)

router = APIRouter(tags=["risks"])


@router.post("/projects/{project_id}/risks", response_model=RiskOut, status_code=201)
def create_risk(
    project_id: uuid.UUID,
    payload: RiskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Risk:
    require_min_role(db, project_id, user.id, min_role="member")
    now = datetime.utcnow()

    code = (payload.code or f"R-{uuid.uuid4().hex[:8].upper()}").strip() or None
    overall_impact = compute_overall_impact(
        payload.impact,
        impact_cost=payload.impact_cost,
        impact_time=payload.impact_time,
        impact_scope=payload.impact_scope,
        impact_quality=payload.impact_quality,
    )

    risk = Risk(
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
        created_by=user.id,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    db.add(risk)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Risk code already exists in this project"
        ) from exc
    db.refresh(risk)
    return risk


@router.get("/projects/{project_id}/risks", response_model=list[RiskOut])
def list_risks(
    project_id: uuid.UUID,
    search: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=25),
    max_score: int | None = Query(default=None, ge=0, le=25),
    status: str | None = None,
    category: str | None = None,
    owner_user_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Risk]:
    ensure_member(db, project_id, user.id)
    stmt = select(Risk).where(Risk.project_id == project_id)
    stmt = apply_item_filters(
        stmt,
        Risk,
        search=search,
        min_score=min_score,
        max_score=max_score,
        status=status,
        category=category,
        owner_user_id=owner_user_id,
        from_date=from_date,
        to_date=to_date,
    )
    stmt = stmt.order_by(Risk.score.desc(), Risk.title.asc())
    return db.execute(stmt).scalars().all()


@router.patch("/projects/{project_id}/risks/{risk_id}", response_model=RiskOut)
def update_risk(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    payload: RiskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Risk:
    require_min_role(db, project_id, user.id, min_role="member")
    now = datetime.utcnow()

    risk = (
        db.execute(
            select(Risk).where(Risk.project_id == project_id, Risk.id == risk_id)
        )
        .scalars()
        .first()
    )
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    if payload.base_version is not None and risk.version != payload.base_version:
        raise HTTPException(
            status_code=409,
            detail={"reason": "version_mismatch", "server_version": risk.version},
        )

    if payload.title is not None:
        risk.title = payload.title
    if payload.probability is not None:
        risk.probability = payload.probability

    if payload.impact_cost is not None:
        risk.impact_cost = payload.impact_cost
    if payload.impact_time is not None:
        risk.impact_time = payload.impact_time
    if payload.impact_scope is not None:
        risk.impact_scope = payload.impact_scope
    if payload.impact_quality is not None:
        risk.impact_quality = payload.impact_quality
    if payload.impact is not None:
        risk.impact = payload.impact

    if payload.code is not None:
        risk.code = payload.code.strip() or None
    if payload.description is not None:
        risk.description = payload.description
    if payload.category is not None:
        risk.category = payload.category
    if payload.threat is not None:
        risk.threat = payload.threat
    if payload.triggers is not None:
        risk.triggers = payload.triggers
    if payload.mitigation_plan is not None:
        risk.mitigation_plan = payload.mitigation_plan
    if payload.document_url is not None:
        risk.document_url = payload.document_url
    if payload.owner_user_id is not None:
        risk.owner_user_id = payload.owner_user_id

    if payload.status is not None:
        new_status = payload.status.value
        if new_status != risk.status:
            risk.status = new_status
            risk.status_changed_at = now

    if payload.identified_at is not None:
        risk.identified_at = payload.identified_at
    if payload.response_at is not None:
        risk.response_at = payload.response_at
    if payload.occurred_at is not None:
        risk.occurred_at = payload.occurred_at

    overall_impact = compute_overall_impact(
        int(risk.impact),
        impact_cost=getattr(risk, "impact_cost", None),
        impact_time=getattr(risk, "impact_time", None),
        impact_scope=getattr(risk, "impact_scope", None),
        impact_quality=getattr(risk, "impact_quality", None),
    )
    risk.impact = overall_impact
    risk.score = compute_score(risk.probability, overall_impact)

    risk.updated_at = now
    risk.version = int(risk.version) + 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Risk code already exists in this project"
        ) from exc

    db.refresh(risk)
    return risk


@router.delete("/projects/{project_id}/risks/{risk_id}", status_code=204)
def delete_risk(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    require_min_role(db, project_id, user.id, min_role="manager")
    risk = (
        db.execute(
            select(Risk).where(Risk.project_id == project_id, Risk.id == risk_id)
        )
        .scalars()
        .first()
    )
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    risk.is_deleted = True
    risk.status = "deleted"
    risk.status_changed_at = datetime.utcnow()
    risk.updated_at = datetime.utcnow()
    risk.version = int(risk.version) + 1
    db.commit()
    return None


@router.get("/projects/{project_id}/risks/report", response_model=ScoreReportOut)
def risks_report(
    project_id: uuid.UUID,
    search: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=25),
    max_score: int | None = Query(default=None, ge=0, le=25),
    status: str | None = None,
    category: str | None = None,
    owner_user_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScoreReportOut:
    ensure_member(db, project_id, user.id)

    base_stmt = select(Risk).where(Risk.project_id == project_id)
    stmt = apply_item_filters(
        base_stmt,
        Risk,
        search=search,
        min_score=min_score,
        max_score=max_score,
        status=status,
        category=category,
        owner_user_id=owner_user_id,
        from_date=from_date,
        to_date=to_date,
    )

    # Total in project with the same deleted semantics (but no other filters)
    total_stmt = apply_item_filters(
        select(func.count(Risk.id)).where(Risk.project_id == project_id),
        Risk,
        search=None,
        min_score=None,
        max_score=None,
        status=status,
        category=None,
        owner_user_id=None,
        from_date=None,
        to_date=None,
    )
    project_total = int(db.execute(total_stmt).scalar_one() or 0)

    subq = stmt.subquery()
    r = subq.c

    total, mn, mx, avg = db.execute(
        select(
            func.count(r.id),
            func.min(r.score),
            func.max(r.score),
            func.avg(r.score),
        )
    ).one()

    status_counts: dict[str, int] = {}
    for st_v, n in db.execute(
        select(r.status, func.count(r.id)).group_by(r.status).order_by(func.count(r.id).desc())
    ).all():
        status_counts[str(st_v or "concept")] = int(n or 0)

    category_counts: dict[str, int] = {}
    for cat_v, n in db.execute(
        select(func.coalesce(r.category, "(none)"), func.count(r.id))
        .group_by(func.coalesce(r.category, "(none)"))
        .order_by(func.count(r.id).desc())
    ).all():
        category_counts[str(cat_v)] = int(n or 0)

    owner_counts: dict[str, int] = {}
    for own_v, n in db.execute(
        select(func.coalesce(cast(r.owner_user_id, String), "(none)"), func.count(r.id))
        .group_by(func.coalesce(cast(r.owner_user_id, String), "(none)"))
        .order_by(func.count(r.id).desc())
    ).all():
        owner_counts[str(own_v)] = int(n or 0)

    bucket = case(
        (r.score <= 4, "0-4"),
        (r.score <= 9, "5-9"),
        (r.score <= 14, "10-14"),
        (r.score <= 19, "15-19"),
        else_="20-25",
    )
    score_buckets: dict[str, int] = {"0-4": 0, "5-9": 0, "10-14": 0, "15-19": 0, "20-25": 0}
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


@router.post(
    "/projects/{project_id}/risks/{risk_id}/assessments",
    response_model=RiskAssessmentOut,
    status_code=201,
)
def create_assessment(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    payload: RiskAssessmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RiskAssessment:
    require_min_role(db, project_id, user.id, min_role="member")

    risk = (
        db.execute(select(Risk).where(Risk.project_id == project_id, Risk.id == risk_id))
        .scalars()
        .first()
    )
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    now = datetime.utcnow()
    assessment = RiskAssessment(
        id=uuid.uuid4(),
        risk_id=risk_id,
        assessor_user_id=user.id,
        probability=payload.probability,
        impact=payload.impact,
        score=compute_score(payload.probability, payload.impact),
        notes=(payload.notes or ""),
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get(
    "/projects/{project_id}/risks/{risk_id}/assessments",
    response_model=list[RiskAssessmentOut],
)
def list_assessments(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RiskAssessment]:
    ensure_member(db, project_id, user.id)

    exists = db.execute(
        select(Risk.id).where(Risk.project_id == project_id, Risk.id == risk_id)
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Risk not found")

    return (
        db.execute(
            select(RiskAssessment)
            .where(
                RiskAssessment.risk_id == risk_id,
                RiskAssessment.is_deleted.is_(False),
            )
            .order_by(RiskAssessment.updated_at.desc())
        )
        .scalars()
        .all()
    )


@router.put(
    "/projects/{project_id}/risks/{risk_id}/assessment",
    response_model=RiskAssessmentOut,
)
def upsert_my_assessment(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    payload: RiskAssessmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RiskAssessment:
    require_min_role(db, project_id, user.id, min_role="member")

    risk = (
        db.execute(
            select(Risk).where(
                Risk.id == risk_id,
                Risk.project_id == project_id,
                Risk.is_deleted.is_(False),
            )
        )
        .scalars()
        .first()
    )
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    existing = (
        db.execute(
            select(RiskAssessment).where(
                RiskAssessment.risk_id == risk_id,
                RiskAssessment.assessor_user_id == user.id,
            )
        )
        .scalars()
        .first()
    )

    now = datetime.utcnow()
    score = compute_score(payload.probability, payload.impact)

    if existing:
        existing.probability = payload.probability
        existing.impact = payload.impact
        existing.score = score
        existing.notes = payload.notes or ""
        existing.is_deleted = False
        existing.updated_at = now
        existing.version = int(existing.version or 0) + 1
        assessment = existing
    else:
        assessment = RiskAssessment(
            id=uuid.uuid4(),
            risk_id=risk_id,
            assessor_user_id=user.id,
            probability=payload.probability,
            impact=payload.impact,
            score=score,
            notes=payload.notes or "",
            created_at=now,
            updated_at=now,
            version=1,
            is_deleted=False,
        )
        db.add(assessment)

    db.commit()
    db.refresh(assessment)
    return assessment
