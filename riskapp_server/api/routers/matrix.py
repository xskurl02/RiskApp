from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
        for r in (
            db.execute(
                select(Risk).where(Risk.project_id == project_id, Risk.is_deleted.is_(False))
            )
            .scalars()
            .all()
        ):
            risks_m[r.probability - 1][r.impact - 1] += 1

    if opps_m is not None:
        for o in (
            db.execute(
                select(Opportunity).where(
                    Opportunity.project_id == project_id,
                    Opportunity.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        ):
            opps_m[o.probability - 1][o.impact - 1] += 1

    return MatrixResponse(
        kind=kind_norm,
        probability_axis=p_axis,
        impact_axis=i_axis,
        risks=risks_m,
        opportunities=opps_m,
    )
