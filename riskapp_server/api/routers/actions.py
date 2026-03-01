from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from core.permissions import ensure_member, require_min_role
from core.items_crud import delete_item
from db import Action, Opportunity, Risk, User, Role, get_db
from schemas import ActionCreate, ActionOut, ActionUpdate

router = APIRouter(tags=["actions"])


@router.post("/projects/{project_id}/actions", response_model=ActionOut, status_code=201)
def create_action(
    project_id: uuid.UUID,
    payload: ActionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Action:
    require_min_role(db, project_id, user.id, min_role=Role.member)

    if (payload.risk_id is None) == (payload.opportunity_id is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of risk_id/opportunity_id",
        )

    # DRY: Determine Target Model dynamically and verify existence in one step
    TargetModel = Risk if payload.risk_id else Opportunity
    target_id = payload.risk_id or payload.opportunity_id
    
    exists = db.execute(
        select(TargetModel.id).where(TargetModel.project_id == project_id, TargetModel.id == target_id)
    ).first()
    if not exists:
        raise HTTPException(status_code=400, detail="Target item not found in this project")

    now = datetime.utcnow()
    action = Action(
        id=uuid.uuid4(),
        project_id=project_id,
        risk_id=payload.risk_id,
        opportunity_id=payload.opportunity_id,
        kind=payload.kind.value,
        title=payload.title,
        description=payload.description,
        status="open",
        owner_user_id=payload.owner_user_id,
        created_by=user.id,
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


@router.get("/projects/{project_id}/actions", response_model=list[ActionOut])
def list_actions(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Action]:
    ensure_member(db, project_id, user.id)
    return (
        db.execute(
            select(Action)
            .where(Action.project_id == project_id, Action.is_deleted.is_(False))
            .order_by(Action.updated_at.desc())
        )
        .scalars()
        .all()
    )

@router.patch("/projects/{project_id}/actions/{action_id}", response_model=ActionOut)
def update_action(
    project_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: ActionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Action:
    require_min_role(db, project_id, user.id, min_role=Role.member)

    action = (
        db.execute(select(Action).where(Action.project_id == project_id, Action.id == action_id))
        .scalars()
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if payload.kind is not None:
        action.kind = payload.kind.value
    if payload.title is not None:
        action.title = payload.title
    if payload.description is not None:
        action.description = payload.description
    if payload.status is not None:
        action.status = payload.status.value
    if payload.owner_user_id is not None:
        action.owner_user_id = payload.owner_user_id

    action.updated_at = datetime.utcnow()
    action.version = int(action.version) + 1
    db.commit()
    db.refresh(action)
    return action


@router.delete("/projects/{project_id}/actions/{action_id}", status_code=204)
def delete_action(
    project_id: uuid.UUID,
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    require_min_role(db, project_id, user.id, min_role=Role.manager)
    return delete_item(db, project_id, action_id, Action)
