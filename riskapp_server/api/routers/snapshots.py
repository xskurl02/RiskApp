from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from core.permissions import ensure_member, require_min_role
from db import Opportunity, Risk, ScoreSnapshot, User, get_db
from schemas import SnapshotCreateOut, TopBatch, TopItem

router = APIRouter(tags=["snapshots"])


@router.post("/projects/{project_id}/snapshots", response_model=SnapshotCreateOut, status_code=201)
def create_snapshot(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SnapshotCreateOut:
    require_min_role(db, project_id, user.id, min_role="member")

    batch_id = uuid.uuid4()
    captured_at = datetime.utcnow()

    risks = (
        db.execute(
            select(Risk).where(Risk.project_id == project_id, Risk.is_deleted.is_(False))
        )
        .scalars()
        .all()
    )
    opps = (
        db.execute(
            select(Opportunity).where(
                Opportunity.project_id == project_id,
                Opportunity.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )

    for r in risks:
        db.add(
            ScoreSnapshot(
                id=uuid.uuid4(),
                batch_id=batch_id,
                captured_at=captured_at,
                project_id=project_id,
                kind="risk",
                item_id=r.id,
                title=r.title,
                probability=r.probability,
                impact=r.impact,
                score=r.score,
                created_by=user.id,
            )
        )

    for o in opps:
        db.add(
            ScoreSnapshot(
                id=uuid.uuid4(),
                batch_id=batch_id,
                captured_at=captured_at,
                project_id=project_id,
                kind="opportunity",
                item_id=o.id,
                title=o.title,
                probability=o.probability,
                impact=o.impact,
                score=o.score,
                created_by=user.id,
            )
        )

    db.commit()
    return SnapshotCreateOut(
        batch_id=batch_id,
        captured_at=captured_at,
        risks=len(risks),
        opportunities=len(opps),
    )


@router.get("/projects/{project_id}/snapshots/{batch_id}/top", response_model=TopBatch)
def top_items(
    project_id: uuid.UUID,
    batch_id: uuid.UUID,
    kind: str = "risk",  # risk|opportunity
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TopBatch:
    ensure_member(db, project_id, user.id)
    limit = max(1, min(limit, 100))

    rows = (
        db.execute(
            select(ScoreSnapshot)
            .where(
                ScoreSnapshot.project_id == project_id,
                ScoreSnapshot.batch_id == batch_id,
                ScoreSnapshot.kind == kind,
            )
            .order_by(ScoreSnapshot.score.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Snapshot batch not found (or empty)")

    return TopBatch(
        batch_id=batch_id,
        captured_at=rows[0].captured_at,
        top=[
            TopItem(
                item_id=r.item_id,
                title=r.title,
                probability=r.probability,
                impact=r.impact,
                score=r.score,
            )
            for r in rows
        ],
    )


@router.get("/projects/{project_id}/top-history", response_model=list[TopBatch])
def top_history(
    project_id: uuid.UUID,
    kind: str = "risks",  # risks|opportunities|risk|opportunity
    limit: int = 10,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TopBatch]:
    ensure_member(db, project_id, user.id)
    limit = max(1, min(limit, 100))

    k = (kind or "").strip().lower()
    if k in {"risks", "risk"}:
        snap_kind = "risk"
    elif k in {"opportunities", "opportunity", "opps", "opp"}:
        snap_kind = "opportunity"
    else:
        raise HTTPException(status_code=400, detail="kind must be risks|opportunities")

    filters = [
        ScoreSnapshot.project_id == project_id,
        ScoreSnapshot.kind == snap_kind,
    ]
    if from_ts is not None:
        filters.append(ScoreSnapshot.captured_at >= from_ts)
    if to_ts is not None:
        filters.append(ScoreSnapshot.captured_at <= to_ts)

    batches = (
        db.execute(
            select(ScoreSnapshot.batch_id, ScoreSnapshot.captured_at)
            .where(*filters)
            .group_by(ScoreSnapshot.batch_id, ScoreSnapshot.captured_at)
            .order_by(ScoreSnapshot.captured_at.asc())
        )
        .all()
    )

    out: list[TopBatch] = []
    for batch, captured_at in batches:
        rows = (
            db.execute(
                select(ScoreSnapshot)
                .where(
                    ScoreSnapshot.project_id == project_id,
                    ScoreSnapshot.batch_id == batch,
                    ScoreSnapshot.kind == snap_kind,
                )
                .order_by(ScoreSnapshot.score.desc(), ScoreSnapshot.title.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        out.append(
            TopBatch(
                batch_id=batch,
                captured_at=captured_at,
                top=[
                    TopItem(
                        item_id=r.item_id,
                        title=r.title,
                        probability=r.probability,
                        impact=r.impact,
                        score=r.score,
                    )
                    for r in rows
                ],
            )
        )

    return out
