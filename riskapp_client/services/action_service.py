"""Action write operations for offline-first mode."""

from __future__ import annotations

import uuid

from riskapp_client.adapters.local.outbox import OutboxStore
from riskapp_client.adapters.local.sqlite_store import LocalStore, utc_iso
from riskapp_client.domain.models import Action


class ActionService:
    """Create/update actions locally and queue sync."""

    def __init__(self, store: LocalStore, outbox: OutboxStore) -> None:
        self._store = store
        self._outbox = outbox

    def list(self, project_id: str) -> list[Action]:
        return self._store.list_actions(project_id)

    def create(
        self,
        project_id: str,
        *,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
    ) -> Action:
        action_id = str(uuid.uuid4())
        risk_id = target_id if target_type == "risk" else None
        opportunity_id = target_id if target_type != "risk" else None

        self._store.upsert_local_action(
            action_id=action_id,
            project_id=project_id,
            risk_id=risk_id,
            opportunity_id=opportunity_id,
            kind=kind,
            title=title,
            description=description or "",
            status=status or "open",
            owner_user_id=owner_user_id,
            version=0,
            is_deleted=False,
            updated_at=utc_iso(),
            dirty=1,
        )
        self._outbox.queue_action_upsert(
            action_id,
            project_id,
            risk_id=risk_id,
            opportunity_id=opportunity_id,
            kind=kind,
            title=title,
            description=description or "",
            status=status or "open",
            owner_user_id=owner_user_id,
        )

        return Action(
            id=action_id,
            project_id=project_id,
            risk_id=risk_id,
            opportunity_id=opportunity_id,
            kind=kind,
            title=title,
            description=description or "",
            status=status or "open",
            owner_user_id=owner_user_id,
            version=0,
        )

    def update(
        self,
        action_id: str,
        *,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
    ) -> Action:
        project_id, version = self._store.get_action_project_and_version(action_id)
        risk_id = target_id if target_type == "risk" else None
        opportunity_id = target_id if target_type != "risk" else None

        self._store.upsert_local_action(
            action_id=action_id,
            project_id=project_id,
            risk_id=risk_id,
            opportunity_id=opportunity_id,
            kind=kind,
            title=title,
            description=description or "",
            status=status or "open",
            owner_user_id=owner_user_id,
            version=version,
            is_deleted=False,
            updated_at=utc_iso(),
            dirty=1,
        )
        self._outbox.queue_action_upsert(
            action_id,
            project_id,
            risk_id=risk_id,
            opportunity_id=opportunity_id,
            kind=kind,
            title=title,
            description=description or "",
            status=status or "open",
            owner_user_id=owner_user_id,
        )

        return Action(
            id=action_id,
            project_id=project_id,
            risk_id=risk_id,
            opportunity_id=opportunity_id,
            kind=kind,
            title=title,
            description=description or "",
            status=status or "open",
            owner_user_id=owner_user_id,
            version=version,
        )
