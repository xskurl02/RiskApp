from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from auth import get_current_user
from core.permissions import ensure_member
from db import Opportunity, Risk, User, get_db
from schemas import MatrixResponse

router = APIRouter(tags=["matrix"])


@router.get("/projects/{project_id}/matrix", response_model=MatrixResponse)
def matrix(
    project_id: uuid.UUID,
    kind: str = "both",  # risk|opportunity|both
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MatrixResponse:
    ensure_member(db, project_id, user.id)

    kind_norm = (kind or "").strip().lower()
    if kind_norm not in {"risk", "opportunity", "both"}:
        raise HTTPException(status_code=400, detail="kind must be risk|opportunity|both")

    p_axis = [1, 2, 3, 4, 5]
    i_axis = [1, 2, 3, 4, 5]

    def blank() -> list[list[int]]:
        return [[0 for _ in i_axis] for __ in p_axis]

    risks_m = blank() if kind_norm in {"risk", "both"} else None
    opps_m = blank() if kind_norm in {"opportunity", "both"} else None

    if risks_m is not None:
        counts = db.execute(
            select(Risk.probability, Risk.impact, func.count(Risk.id))
            .where(Risk.project_id == project_id, Risk.is_deleted.is_(False))
            .group_by(Risk.probability, Risk.impact)
        ).all()
        for p, i, count in counts:
            risks_m[p - 1][i - 1] = count

    if opps_m is not None:
        counts = db.execute(
            select(Opportunity.probability, Opportunity.impact, func.count(Opportunity.id))
            .where(Opportunity.project_id == project_id, Opportunity.is_deleted.is_(False))
            .group_by(Opportunity.probability, Opportunity.impact)
        ).all()
        for p, i, count in counts:
            opps_m[p - 1][i - 1] = count

    return MatrixResponse(
        kind=kind_norm,
        probability_axis=p_axis,
        impact_axis=i_axis,
        risks=risks_m,
        opportunities=opps_m,
    )
