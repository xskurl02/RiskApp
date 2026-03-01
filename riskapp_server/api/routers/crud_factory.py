from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import get_current_user
from core.permissions import ensure_member, require_min_role
from core.items_crud import create_item, update_item, list_items, delete_item, generate_report
from db import User, get_db
from schemas import ScoreReportOut

def create_crud_router(
    prefix: str,
    tags: list[str],
    Model,
    CreateSchema,
    UpdateSchema,
    OutSchema,
) -> APIRouter:
    router = APIRouter(tags=tags)

    @router.post(f"/projects/{{project_id}}/{prefix}", response_model=OutSchema, status_code=201)
    def create_obj(
        project_id: uuid.UUID,
        payload: CreateSchema,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        require_min_role(db, project_id, user.id, min_role="member")
        return create_item(db, user.id, project_id, payload, Model)

    @router.get(f"/projects/{{project_id}}/{prefix}", response_model=list[OutSchema])
    def list_objs(
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
    ):
        ensure_member(db, project_id, user.id)
        filters = {
            "search": search, "min_score": min_score, "max_score": max_score,
            "status": status, "category": category, "owner_user_id": owner_user_id,
            "from_date": from_date, "to_date": to_date
        }
        return list_items(db, project_id, Model, filters)

    @router.patch(f"/projects/{{project_id}}/{prefix}/{{item_id}}", response_model=OutSchema)
    def update_obj(
        project_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: UpdateSchema,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        require_min_role(db, project_id, user.id, min_role="member")
        return update_item(db, project_id, item_id, payload, Model)

    @router.delete(f"/projects/{{project_id}}/{prefix}/{{item_id}}", status_code=204)
    def delete_obj(
        project_id: uuid.UUID,
        item_id: uuid.UUID,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> None:
        require_min_role(db, project_id, user.id, min_role="manager")
        return delete_item(db, project_id, item_id, Model)

    @router.get(f"/projects/{{project_id}}/{prefix}/report", response_model=ScoreReportOut)
    def obj_report(
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
    ):
        ensure_member(db, project_id, user.id)
        filters = {
            "search": search, "min_score": min_score, "max_score": max_score,
            "status": status, "category": category, "owner_user_id": owner_user_id,
            "from_date": from_date, "to_date": to_date
        }
        return generate_report(db, project_id, Model, filters)

    return router