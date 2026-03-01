from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from core.permissions import ensure_member, require_min_role
from db import Project, ProjectMember, User, Role, get_db
from schemas import AddMemberIn, MemberOut, ProjectCreate, ProjectOut

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    now = datetime.utcnow()
    project = Project(
        name=payload.name,
        description=payload.description,
        created_at=now,
        created_by=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=Role.admin.value, created_at=now))
    db.commit()
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Project]:
    return (
        db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(Project.created_at.desc())
        )
        .scalars()
        .all()
    )


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    ensure_member(db, project_id, user.id)
    proj = db.execute(select(Project).where(Project.id == project_id)).scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.post("/projects/{project_id}/members", status_code=201)
def add_member(
    project_id: uuid.UUID,
    payload: AddMemberIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    require_min_role(db, project_id, user.id, min_role=Role.admin)

    target = (
        db.execute(select(User).where(User.email == str(payload.user_email))).scalars().first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == target.id,
            )
        )
        .scalars()
        .first()
    )

    if existing:
        existing.role = payload.role.value
        db.commit()
        return {"ok": True, "updated": True}

    db.add(
        ProjectMember(
            project_id=project_id,
            user_id=target.id,
            role=payload.role.value,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    return {"ok": True, "updated": False}


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def list_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MemberOut]:
    ensure_member(db, project_id, user.id)
    rows = (
        db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(User.email.asc())
        )
        .all()
    )
    return [
        MemberOut(
            user_id=u.id,
            email=u.email,
            role=pm.role,  # type: ignore[arg-type]
            created_at=getattr(pm, "created_at", None),
        )
        for pm, u in rows
    ]


@router.delete("/projects/{project_id}/members/{member_user_id}", status_code=204)
def remove_member(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    require_min_role(db, project_id, user.id, min_role=Role.admin)
    m = (
        db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == member_user_id,
            )
        )
        .scalars()
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(m)
    db.commit()
    return None
