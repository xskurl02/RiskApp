from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...core.permissions import ensure_member
from ...db import Opportunity, Risk, User, get_db
from ...schemas import MatrixResponse

router = APIRouter(tags=["matrix"])


@router.get("/projects/{project_id}/matrix", response_model=MatrixResponse)
def matrix(
    project_id: uuid.UUID,
    kind: str = "both",  # risk|opportunity|both
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MatrixResponse:
    ensure_member(db, project_id, user.id)

    k = (kind or "").strip().lower()
    if k not in {"risk", "opportunity", "both"}:
        raise HTTPException(status_code=400, detail="kind must be risk|opportunity|both")

    p_axis = list(range(1, 6))
    i_axis = list(range(1, 6))

    def blank() -> list[list[int]]:
        return [[0 for _ in i_axis] for __ in p_axis]

    risks = blank() if k in {"risk", "both"} else None
    opps = blank() if k in {"opportunity", "both"} else None

    def fill(Model, out):
        if out is None:
            return
        for p, i, c in db.execute(
            select(Model.probability, Model.impact, func.count(Model.id))
            .where(Model.project_id == project_id, Model.is_deleted.is_(False))
            .group_by(Model.probability, Model.impact)
        ).all():
            out[p - 1][i - 1] = c

    fill(Risk, risks)
    fill(Opportunity, opps)

    return MatrixResponse(kind=k, probability_axis=p_axis, impact_axis=i_axis, risks=risks, opportunities=opps)
