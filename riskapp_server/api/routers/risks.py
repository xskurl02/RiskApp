from __future__ import annotations

import uuid

from datetime import datetime
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.routers.crud_factory import create_crud_router
from auth import get_current_user
from core.permissions import ensure_member, require_min_role
from core.scoring import compute_score
from db import Risk, RiskAssessment, User, get_db
from schemas import (
    RiskAssessmentIn,
    RiskAssessmentOut,
    RiskCreate,
    RiskOut,
    RiskUpdate,
)

router = create_crud_router(
    prefix="risks",
    tags=["risks"],
    Model=Risk,
    CreateSchema=RiskCreate,
    UpdateSchema=RiskUpdate,
    OutSchema=RiskOut,
)

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
