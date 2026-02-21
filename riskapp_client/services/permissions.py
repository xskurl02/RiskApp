"""Role/permission helpers shared by the Qt UI."""

from __future__ import annotations

ROLE_RANK = {"viewer": 1, "member": 2, "manager": 3, "admin": 4}

def role_at_least(role: str, min_role: str) -> bool:
    """Return True if `role` is >= `min_role` using ROLE_RANK."""
    role_key = (role or "").strip().lower()
    min_key = (min_role or "").strip().lower()
    return ROLE_RANK.get(role_key, 0) >= ROLE_RANK.get(min_key, 999)
