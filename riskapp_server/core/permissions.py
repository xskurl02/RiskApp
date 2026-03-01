"""Authorization helpers.

Kept separate from the JWT logic so it can be reused by:
- API endpoints (routers)
- the sync engine (server-side defense-in-depth)
"""

from __future__ import annotations

import uuid
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import ProjectMember, Role

ROLE_RANK: dict[str, int] = {Role.viewer.value: 1, Role.member.value: 2, Role.manager.value: 3, Role.admin.value: 4}


def ensure_role_at_least(role: str | Role, min_role: str | Role) -> None:
    """Raise 403 if `role` is below `min_role`."""
    r_val = role.value if isinstance(role, Role) else role
    m_val = min_role.value if isinstance(min_role, Role) else min_role
    if ROLE_RANK.get(r_val, 0) < ROLE_RANK.get(m_val, 10_000):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def get_member_role(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    row = db.execute(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).first()
    return str(row[0]) if row else None


def require_project_role(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    allowed: Iterable[str],
) -> str:
    role = get_member_role(db, project_id, user_id)
    allowed_set = set(allowed)
    if not role or role not in allowed_set:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return role


def require_min_role(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    min_role: Role | str,
) -> str:
    role = require_project_role(
        db,
        project_id,
        user_id,
        allowed=ROLE_RANK.keys(),
    )
    ensure_role_at_least(role, min_role)
    return role


def ensure_member(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return require_min_role(db, project_id, user_id, min_role=Role.viewer)


def require_project_member(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Return role, or raise if not a member."""
    role = get_member_role(db, project_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member of this project")
    return role
