from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from core.filters import apply_item_filters
from core.permissions import ensure_member, require_min_role
from core.scoring import compute_overall_impact, compute_score
from db import Opportunity, User, get_db
from schemas import OpportunityCreate, OpportunityOut, OpportunityUpdate

router = APIRouter(tags=["opportunities"])


@router.post("/projects/{project_id}/opportunities", response_model=OpportunityOut, status_code=201)
def create_opportunity(
    project_id: uuid.UUID,
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Opportunity:
    require_min_role(db, project_id, user.id, min_role="member")
    now = datetime.utcnow()

    code = (payload.code or f"O-{uuid.uuid4().hex[:8].upper()}").strip() or None
    overall_impact = compute_overall_impact(
        payload.impact,
        impact_cost=payload.impact_cost,
        impact_time=payload.impact_time,
        impact_scope=payload.impact_scope,
        impact_quality=payload.impact_quality,
    )

    opp = Opportunity(
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

    db.add(opp)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Opportunity code already exists in this project"
        ) from exc
    db.refresh(opp)
    return opp


@router.get("/projects/{project_id}/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
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
) -> list[Opportunity]:
    ensure_member(db, project_id, user.id)
    stmt = select(Opportunity).where(Opportunity.project_id == project_id)
    stmt = apply_item_filters(
        stmt,
        Opportunity,
        search=search,
        min_score=min_score,
        max_score=max_score,
        status=status,
        category=category,
        owner_user_id=owner_user_id,
        from_date=from_date,
        to_date=to_date,
    )
    stmt = stmt.order_by(Opportunity.score.desc(), Opportunity.title.asc())
    return db.execute(stmt).scalars().all()


@router.patch("/projects/{project_id}/opportunities/{opportunity_id}", response_model=OpportunityOut)
def update_opportunity(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    payload: OpportunityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Opportunity:
    require_min_role(db, project_id, user.id, min_role="member")
    opp = (
        db.execute(
            select(Opportunity).where(
                Opportunity.project_id == project_id, Opportunity.id == opportunity_id
            )
        )
        .scalars()
        .first()
    )
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if payload.base_version is not None and opp.version != payload.base_version:
        raise HTTPException(
            status_code=409, detail={"reason": "version_mismatch", "server_version": opp.version}
        )

    now = datetime.utcnow()

    if payload.title is not None:
        opp.title = payload.title
    if payload.probability is not None:
        opp.probability = payload.probability

    if payload.impact_cost is not None:
        opp.impact_cost = payload.impact_cost
    if payload.impact_time is not None:
        opp.impact_time = payload.impact_time
    if payload.impact_scope is not None:
        opp.impact_scope = payload.impact_scope
    if payload.impact_quality is not None:
        opp.impact_quality = payload.impact_quality
    if payload.impact is not None:
        opp.impact = payload.impact

    if payload.code is not None:
        opp.code = payload.code.strip() or None
    if payload.description is not None:
        opp.description = payload.description
    if payload.category is not None:
        opp.category = payload.category
    if payload.threat is not None:
        opp.threat = payload.threat
    if payload.triggers is not None:
        opp.triggers = payload.triggers
    if payload.mitigation_plan is not None:
        opp.mitigation_plan = payload.mitigation_plan
    if payload.document_url is not None:
        opp.document_url = payload.document_url
    if payload.owner_user_id is not None:
        opp.owner_user_id = payload.owner_user_id

    if payload.status is not None:
        new_status = payload.status.value
        if new_status != opp.status:
            opp.status = new_status
            opp.status_changed_at = now

    if payload.identified_at is not None:
        opp.identified_at = payload.identified_at
    if payload.response_at is not None:
        opp.response_at = payload.response_at
    if payload.occurred_at is not None:
        opp.occurred_at = payload.occurred_at

    overall_impact = compute_overall_impact(
        int(opp.impact),
        impact_cost=getattr(opp, "impact_cost", None),
        impact_time=getattr(opp, "impact_time", None),
        impact_scope=getattr(opp, "impact_scope", None),
        impact_quality=getattr(opp, "impact_quality", None),
    )
    opp.impact = overall_impact
    opp.score = compute_score(opp.probability, overall_impact)

    opp.updated_at = now
    opp.version = int(opp.version) + 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Opportunity code already exists in this project"
        ) from exc

    db.refresh(opp)
    return opp


@router.delete("/projects/{project_id}/opportunities/{opportunity_id}", status_code=204)
def delete_opportunity(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    require_min_role(db, project_id, user.id, min_role="manager")
    opp = (
        db.execute(
            select(Opportunity).where(
                Opportunity.project_id == project_id, Opportunity.id == opportunity_id
            )
        )
        .scalars()
        .first()
    )
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opp.is_deleted = True
    opp.status = "deleted"
    opp.status_changed_at = datetime.utcnow()
    opp.updated_at = datetime.utcnow()
    opp.version = int(opp.version) + 1
    db.commit()
    return None
