"""Authorization helpers (used by both routers and the sync engine)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from riskapp_server.db.session import ProjectMember, Role

ROLE_RANK: dict[str, int] = {
    Role.viewer.value: 1,
    Role.member.value: 2,
    Role.manager.value: 3,
    Role.admin.value: 4,
}


def ensure_role_at_least(role: str | Role, min_role: str | Role) -> None:
    """Ensure role at least."""
    r = role.value if isinstance(role, Role) else role
    m = min_role.value if isinstance(min_role, Role) else min_role
    if ROLE_RANK.get(r, 0) < ROLE_RANK.get(m, 10_000):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def get_member_role(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Return member role."""

    def _normalize_role(val) -> str | None:
        """Internal helper for normalize role."""
        if val is None:
            return None
        if isinstance(val, Role):
            return val.value

        # Depending on how the SQLAlchemy column is declared, we may get back:
        # - a plain string ("admin")
        # - an Enum instance (Role.admin)
        # - a stringified Enum ("Role.admin")
        s = str(val)
        if s.startswith("Role."):
            candidate = s.split(".", 1)[1]
            if candidate in ROLE_RANK:
                return candidate
        return s

    row = db.execute(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).first()
    return _normalize_role(row[0]) if row else None


def require_min_role(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    min_role: Role | str,
) -> str:
    """Handle require min role."""
    role = get_member_role(db, project_id, user_id)
    if not role or role not in ROLE_RANK:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    ensure_role_at_least(role, min_role)
    return role


def ensure_member(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Ensure member."""
    return require_min_role(db, project_id, user_id, min_role=Role.viewer)
