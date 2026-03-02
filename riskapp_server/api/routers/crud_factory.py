from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...core.filters import ItemFilterParams
from ...core.items_crud import create_item, delete_item, generate_report, list_items, update_item
from ...core.permissions import ensure_member, require_min_role
from ...core.scoring import recalculate_item_scores
from ...db import User, get_db, utcnow
from ...schemas import ScoreReportOut, AssessmentIn


def create_crud_router(*, prefix: str, tags: list[str], Model, CreateSchema, UpdateSchema, OutSchema, AssessmentModel=None, AssessmentOutSchema=None) -> APIRouter:
    r = APIRouter(tags=tags)

    @r.post(f"/projects/{{project_id}}/{prefix}", response_model=OutSchema, status_code=201)
    def create_obj(
        project_id: uuid.UUID,
        payload: CreateSchema,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        require_min_role(db, project_id, user.id, min_role="member")
        return create_item(db, user.id, project_id, payload, Model)

    @r.get(f"/projects/{{project_id}}/{prefix}", response_model=list[OutSchema])
    def list_objs(
        project_id: uuid.UUID,
        filters: ItemFilterParams = Depends(),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        ensure_member(db, project_id, user.id)
        return list_items(db, project_id, Model, vars(filters))

    @r.patch(f"/projects/{{project_id}}/{prefix}/{{item_id}}", response_model=OutSchema)
    def update_obj(
        project_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: UpdateSchema,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        require_min_role(db, project_id, user.id, min_role="member")
        return update_item(db, project_id, item_id, payload, Model)

    @r.delete(f"/projects/{{project_id}}/{prefix}/{{item_id}}", status_code=204)
    def delete_obj(
        project_id: uuid.UUID,
        item_id: uuid.UUID,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> None:
        require_min_role(db, project_id, user.id, min_role="manager")
        return delete_item(db, project_id, item_id, Model)

    @r.get(f"/projects/{{project_id}}/{prefix}/report", response_model=ScoreReportOut)
    def obj_report(
        project_id: uuid.UUID,
        filters: ItemFilterParams = Depends(),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        ensure_member(db, project_id, user.id)
        return generate_report(db, project_id, Model, vars(filters))

    if AssessmentModel and AssessmentOutSchema:
        parent_id_field = f"{Model.__name__.lower()}_id"

        @r.get(f"/projects/{{project_id}}/{prefix}/{{item_id}}/assessments", response_model=list[AssessmentOutSchema])
        def list_assessments(project_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
            ensure_member(db, project_id, user.id)
            if not db.execute(select(Model.id).where(Model.project_id == project_id, Model.id == item_id)).first():
                raise HTTPException(status_code=404, detail="Item not found")
            return db.execute(
                select(AssessmentModel).where(getattr(AssessmentModel, parent_id_field) == item_id, AssessmentModel.is_deleted.is_(False)).order_by(AssessmentModel.updated_at.desc())
            ).scalars().all()

        @r.put(f"/projects/{{project_id}}/{prefix}/{{item_id}}/assessment", response_model=AssessmentOutSchema)
        def upsert_my_assessment(project_id: uuid.UUID, item_id: uuid.UUID, payload: AssessmentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
            require_min_role(db, project_id, user.id, min_role="member")
            if not db.execute(select(Model.id).where(Model.id == item_id, Model.project_id == project_id, Model.is_deleted.is_(False))).first():
                raise HTTPException(status_code=404, detail="Item not found")

            assessment = db.execute(
                select(AssessmentModel).where(getattr(AssessmentModel, parent_id_field) == item_id, AssessmentModel.assessor_user_id == user.id)
            ).scalars().first()

            now = utcnow()
            if not assessment:
                kwargs = {"id": uuid.uuid4(), parent_id_field: item_id, "assessor_user_id": user.id, "created_at": now, "updated_at": now, "version": 0, "is_deleted": False}
                assessment = AssessmentModel(**kwargs)
                db.add(assessment)
            elif payload.base_version is not None and assessment.version != payload.base_version:
                raise HTTPException(status_code=409, detail={"reason": "version_mismatch", "server_version": assessment.version})

            assessment.probability = payload.probability
            assessment.impact = payload.impact
            assessment.notes = payload.notes
            assessment.is_deleted = False
            assessment.updated_at = now
            assessment.version = int(assessment.version) + 1

            recalculate_item_scores(assessment)
            db.commit()
            db.refresh(assessment)
            return assessment
    
    return r
