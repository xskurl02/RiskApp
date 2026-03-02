from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...core.items_crud import delete_item
from ...core.permissions import ensure_member, require_min_role
from ...db import Action, ActionStatus, Item, Role, User, get_db, utcnow
from ...schemas import ActionCreate, ActionOut, ActionUpdate

router = APIRouter(tags=["actions"])


@router.post(
    "/projects/{project_id}/actions", response_model=ActionOut, status_code=201
)
def create_action(
    project_id: uuid.UUID,
    payload: ActionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Action:
    require_min_role(db, project_id, user.id, min_role=Role.member)
    if not db.execute(
        select(Item.id).where(Item.project_id == project_id, Item.id == payload.item_id)
    ).first():
        raise HTTPException(
            status_code=400, detail="Target item not found in this project"
        )

    now = utcnow()
    data = payload.model_dump()
    data.update(
        {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "status": ActionStatus.open.value,
            "created_by": user.id,
            "created_at": now,
            "updated_at": now,
            "version": 1,
            "is_deleted": False,
        }
    )
    action = Action(**data)
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
        db.execute(
            select(Action).where(
                Action.project_id == project_id, Action.id == action_id
            )
        )
        .scalars()
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(action, field, getattr(val, "value", val))

    action.updated_at = utcnow()
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
