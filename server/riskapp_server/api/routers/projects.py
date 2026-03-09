"""API router for projects."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from riskapp_server.auth.service import get_current_user
from riskapp_server.core.config import RETENTION_DAYS
from riskapp_server.core.permissions import ensure_member, require_min_role
from riskapp_server.db.session import (
    AuditLog,
    Project,
    ProjectMember,
    Role,
    SyncReceipt,
    User,
    get_db,
    utcnow,
)
from riskapp_server.schemas.models import (
    AddMemberIn,
    MemberOut,
    ProjectCreate,
    ProjectOut,
)

router = APIRouter(tags=["projects"])


def _ensure_not_last_admin(db: Session, project_id: uuid.UUID) -> None:
    """Internal helper for ensure not last admin."""
    n = db.execute(
        select(func.count()).where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == Role.admin.value,
        )
    ).scalar()
    if (n or 0) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot downgrade or remove the last admin of the project",
        )


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    """Create project."""
    now = utcnow()
    project = Project(
        id=uuid.uuid4(),
        created_at=now,
        created_by=user.id,
        **payload.model_dump(exclude_unset=True),
    )
    db.add(project)
    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=Role.admin.value,
            created_at=now,
        )
    )
    db.commit()
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Project]:
    """Return projects."""
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
    """Return project."""
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
    """Add member."""
    require_min_role(db, project_id, user.id, min_role=Role.admin)

    target_email = str(payload.user_email).lower()
    target = (
        db.execute(select(User).where(User.email == target_email)).scalars().first()
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
        if existing.role == Role.admin.value and payload.role.value != Role.admin.value:
            _ensure_not_last_admin(db, project_id)
        existing.role = payload.role.value
        db.commit()
        return {"ok": True, "updated": True}

    db.add(
        ProjectMember(
            project_id=project_id,
            user_id=target.id,
            role=payload.role.value,
            created_at=utcnow(),
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
    """Return members."""
    ensure_member(db, project_id, user.id)
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.email.asc())
    ).all()
    return [
        MemberOut(
            user_id=u.id,
            email=u.email,
            role=pm.role,
            created_at=getattr(pm, "created_at", None),
        )
        for pm, u in rows
    ]


@router.delete(
    "/projects/{project_id}/members/{member_user_id}",
    status_code=204,
    response_class=Response,
)
def remove_member(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Remove member."""
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

    if m.role == Role.admin.value:
        _ensure_not_last_admin(db, project_id)

    db.delete(m)
    db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/maintenance/prune")
def prune_project_logs(
    project_id: uuid.UUID,
    days: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete old audit/sync receipt rows for a project.

    This keeps long-running projects from accumulating unbounded log tables.
    """
    require_min_role(db, project_id, user.id, min_role=Role.admin)
    d = int(days or RETENTION_DAYS)
    d = max(1, min(d, 3650))
    cutoff = utcnow() - timedelta(days=d)

    r1 = db.execute(
        delete(AuditLog).where(AuditLog.project_id == project_id, AuditLog.ts < cutoff)
    )
    r2 = db.execute(
        delete(SyncReceipt).where(
            SyncReceipt.project_id == project_id, SyncReceipt.processed_at < cutoff
        )
    )
    db.commit()
    return {
        "ok": True,
        "cutoff": cutoff.isoformat(),
        "audit_deleted": int(getattr(r1, "rowcount", 0) or 0),
        "sync_receipts_deleted": int(getattr(r2, "rowcount", 0) or 0),
    }
