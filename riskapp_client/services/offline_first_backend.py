"""Offline-first backend facade for the Qt client.

Design goals:
- UI reads/writes the local SQLite store.
- Sync is explicit (button): push outbox, then pull changes.

This class is intentionally *thin* and delegates business logic to per-entity
services. That keeps the public UI API stable while allowing small, testable
modules.
"""

from __future__ import annotations

from typing import Any, Optional

from riskapp_client.adapters.local.outbox import OutboxStore
from riskapp_client.adapters.local.sqlite_store import LocalStore
from riskapp_client.domain.models import (
    Action,
    Assessment,
    Backend,
    Member,
    Opportunity,
    Project,
    Risk,
)
from riskapp_client.services.action_service import ActionService
from riskapp_client.services.assessment_service import AssessmentService
from riskapp_client.services.members_service import MembersService
from riskapp_client.services.opportunity_service import OpportunityService
from riskapp_client.services.risk_service import RiskService
from riskapp_client.services.sync_service import SyncService


class OfflineFirstBackend(Backend):
    """Backend implementation used by the Qt UI in offline-first mode."""

    def __init__(self, store: LocalStore, remote: Optional[Any] = None) -> None:
        self.store = store
        self.remote = remote
        self.outbox = OutboxStore(store)

        self._risks = RiskService(store, self.outbox)
        self._opps = OpportunityService(store, self.outbox)
        self._actions = ActionService(store, self.outbox)
        self._assessments = AssessmentService(store, self.outbox)
        self._members = MembersService(remote)
        self._sync = SyncService(store, self.outbox, remote)

    # ---- Projects ----

    def list_projects(self) -> list[Project]:
        if self.remote:
            try:
                projects = self.remote.list_projects()
                self.store.upsert_projects(projects)
            except Exception:  # noqa: BLE001 - offline fallback
                pass
        return self.store.list_projects()

    # ---- Members ----

    def list_members(self, project_id: str) -> list[Member]:
        return self._members.list(project_id)

    def add_member(self, project_id: str, *, user_email: str, role: str) -> None:
        self._members.add(project_id, user_email=user_email, role=role)

    def remove_member(self, project_id: str, *, member_user_id: str) -> None:
        self._members.remove(project_id, member_user_id=member_user_id)

    # ---- Risks ----

    def list_risks(self, project_id: str) -> list[Risk]:
        return self._risks.list(project_id)

    def create_risk(self, project_id: str, *, title: str, probability: int, impact: int, **meta) -> Risk:
        return self._risks.create(
            project_id,
            title=title,
            probability=probability,
            impact=impact,
            meta=meta,
        )

    def update_risk(self, risk_id: str, *, title: str, probability: int, impact: int, **meta) -> Risk:
        return self._risks.update(
            risk_id,
            title=title,
            probability=probability,
            impact=impact,
            meta=meta,
        )

    # ---- Opportunities ----

    def list_opportunities(self, project_id: str) -> list[Opportunity]:
        return self._opps.list(project_id)

    def create_opportunity(
        self, project_id: str, *, title: str, probability: int, impact: int, **meta
    ) -> Opportunity:
        return self._opps.create(
            project_id,
            title=title,
            probability=probability,
            impact=impact,
            meta=meta,
        )

    def update_opportunity(
        self, opportunity_id: str, *, title: str, probability: int, impact: int, **meta
    ) -> Opportunity:
        return self._opps.update(
            opportunity_id,
            title=title,
            probability=probability,
            impact=impact,
            meta=meta,
        )

    # ---- Actions ----

    def list_actions(self, project_id: str) -> list[Action]:
        return self._actions.list(project_id)

    def create_action(
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
        return self._actions.create(
            project_id,
            target_type=target_type,
            target_id=target_id,
            kind=kind,
            title=title,
            description=description,
            status=status,
            owner_user_id=owner_user_id,
        )

    def update_action(
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
        return self._actions.update(
            action_id,
            target_type=target_type,
            target_id=target_id,
            kind=kind,
            title=title,
            description=description,
            status=status,
            owner_user_id=owner_user_id,
        )

    # ---- Assessments ----

    def current_user_id(self) -> str | None:
        if self.remote and getattr(self.remote, "current_user_id", None):
            uid = self.remote.current_user_id()
            if uid:
                self.store.set_meta("user_id", uid)
                return uid
        return self.store.get_meta("user_id")

    def list_assessments(self, project_id: str, risk_id: str) -> list[Assessment]:
        return self._assessments.list(project_id, risk_id)

    def upsert_my_assessment(
        self,
        project_id: str,
        risk_id: str,
        probability: int,
        impact: int,
        notes: str | None = None,
    ) -> Assessment:
        uid = self.current_user_id()
        if not uid:
            raise ValueError("No user_id available (log in online at least once).")
        return self._assessments.upsert_my(
            project_id,
            risk_id,
            uid,
            probability,
            impact,
            notes,
        )

    # ---- Snapshots / history ----

    def create_snapshot(self, project_id: str):
        if not self.remote:
            raise RuntimeError("Snapshots require online mode.")
        return self.remote.create_snapshot(project_id)

    def top_history(
        self,
        project_id: str,
        *,
        kind: str = "risks",
        limit: int = 10,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ):
        if not self.remote:
            return []
        return self.remote.top_history(project_id, kind=kind, limit=limit, from_ts=from_ts, to_ts=to_ts)

    # ---- Sync ----

    def pending_count(self, project_id: str | None = None) -> int:
        return self._sync.pending_count(project_id)

    def can_sync(self) -> bool:
        return self._sync.can_sync()

    def sync_project(self, project_id: str):
        return self._sync.sync_project(project_id)
