"""Members/roles operations.

These require online mode and delegate to the remote API.
"""

from __future__ import annotations

from typing import Any

from riskapp_client.domain.domain_models import Member


class MembersService:
    """Wrap remote member operations with a consistent error surface."""

    def __init__(self, remote: Any | None) -> None:
        self._remote = remote

    def list(self, project_id: str) -> list[Member]:
        if not self._remote:
            return []
        return self._remote.list_members(project_id)

    def add(self, project_id: str, *, user_email: str, role: str) -> None:
        if not self._remote:
            raise RuntimeError("Members/roles management requires online mode.")
        self._remote.add_member(project_id, user_email=user_email, role=role)

    def remove(self, project_id: str, *, member_user_id: str) -> None:
        if not self._remote:
            raise RuntimeError("Members/roles management requires online mode.")
        self._remote.remove_member(project_id, member_user_id=member_user_id)
