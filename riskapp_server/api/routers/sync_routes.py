from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import sync as sync_engine
from auth import get_current_user
from core.permissions import ensure_member, require_min_role
from db import User, get_db
from schemas import SyncPullRequest, SyncPullResponse, SyncPushRequest, SyncPushResponse

router = APIRouter(tags=["sync"])


@router.post("/projects/{project_id}/sync/pull", response_model=SyncPullResponse)
def sync_pull(
    project_id: uuid.UUID,
    payload: SyncPullRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_member(db, project_id, user.id)
    return sync_engine.pull_since(db, project_id=project_id, since=payload.since)


@router.post("/projects/{project_id}/sync/push", response_model=SyncPushResponse)
def sync_push(
    project_id: uuid.UUID,
    payload: SyncPushRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    require_min_role(db, project_id, user.id, min_role="member")
    return sync_engine.push_changes(
        db=db,
        user_id=user.id,
        project_id=project_id,
        changes=[c.model_dump() for c in payload.changes],
    )
