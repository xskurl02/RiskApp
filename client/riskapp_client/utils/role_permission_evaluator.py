"""Role/permission helpers shared by the client UI.

The project requirements include a *hierarchy of permissions*.
This module provides a simple role-rank mapping and comparison helpers.

Notes:
- The server must remain the source of truth for authorization.
- The client can use these helpers for UX (show/hide actions, optimistic UI).
"""

from __future__ import annotations

from typing import Final

# Keep the role names short and stable: these are often persisted in tokens or
# stored in local offline SQLite state.
ROLE_RANK: Final[dict[str, int]] = {"viewer": 1, "member": 2, "manager": 3, "admin": 4}

# Backward-compat for older imports; prefer ROLE_RANK + is_known_role().
UNKNOWN_ROLE_RANK: Final[int] = 999


def normalize_role(role: str | None) -> str:
    """Normalize a role string for comparisons."""
    return (role or "").strip().lower()


def is_known_role(role: str | None) -> bool:
    """Return True if `role` is one of the known role keys."""
    return normalize_role(role) in ROLE_RANK


def role_at_least(role: str | None, min_role: str | None) -> bool:
    """Return True if `role` is >= `min_role` using ROLE_RANK.

    Security-by-default behavior:
    - Unknown/empty `min_role` => False (deny).
    - Unknown/empty `role` => treated as rank 0 (deny).

    If you need a more permissive behavior (e.g., treat empty min_role as
    "viewer"), implement that at the call-site explicitly.
    """

    role_key = normalize_role(role)
    min_key = normalize_role(min_role)

    min_rank = ROLE_RANK.get(min_key)
    if min_rank is None:
        return False

    return ROLE_RANK.get(role_key, 0) >= min_rank
