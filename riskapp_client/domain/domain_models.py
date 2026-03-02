# models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from riskapp_client.domain.scored_entity_fields import (
    ACTION_DEFAULT_STATUS,
    DEFAULT_STATUS,
)


@dataclass
class Member:
    user_id: str
    email: str
    role: str
    created_at: str | None = None


@dataclass
class Project:
    id: str
    name: str
    description: str = ""


@dataclass
class Action:
    id: str
    project_id: str
    risk_id: str | None
    opportunity_id: str | None

    kind: str  # mitigation|contingency|exploit
    title: str
    description: str = ""
    status: str = ACTION_DEFAULT_STATUS
    owner_user_id: str | None = None

    # sync metadata
    version: int = 0
    is_deleted: bool = False
    updated_at: str = ""


@dataclass
class ScoredEntity:
    id: str
    project_id: str

    # Required / assignment fields
    code: str | None = None
    title: str = ""
    description: str | None = None
    category: str | None = None
    threat: str | None = None
    triggers: str | None = None
    mitigation_plan: str | None = None
    document_url: str | None = None
    owner_user_id: str | None = None
    status: str | None = DEFAULT_STATUS

    identified_at: str | None = None
    status_changed_at: str | None = None
    response_at: str | None = None
    occurred_at: str | None = None

    probability: int = 3
    impact: int = 3
    impact_cost: int | None = None
    impact_time: int | None = None
    impact_scope: int | None = None
    impact_quality: int | None = None

    # sync metadata
    version: int = 0
    is_deleted: bool = False
    updated_at: str = ""

    score: int = field(init=False)

    def __post_init__(self) -> None:
        dims = [
            self.impact_cost,
            self.impact_time,
            self.impact_scope,
            self.impact_quality,
        ]
        dims = [int(x) for x in dims if x is not None]
        if dims:
            self.impact = max(dims)
        self.score = int(self.probability) * int(self.impact)


@dataclass
class Risk(ScoredEntity):
    pass


@dataclass
class Opportunity(ScoredEntity):
    pass


@dataclass
class Assessment:
    id: str
    risk_id: str
    assessor_user_id: str
    probability: int
    impact: int
    notes: str = ""

    # sync metadata
    version: int = 0
    is_deleted: bool = False
    updated_at: str = ""

    # allow passing score, but always recompute it
    score: int = 0

    def __post_init__(self) -> None:
        self.score = int(self.probability) * int(self.impact)


class Backend(Protocol):
    def list_projects(self) -> List[Project]: ...

    # --- Risks ---
    def list_risks(self, project_id: str) -> List[Risk]: ...
    def create_risk(
        self,
        project_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = None,
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
    ) -> Risk: ...

    def update_risk(
        self,
        project_id: str,
        risk_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = None,
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
        base_version: int | None = None,
    ) -> Risk: ...

    # --- Opportunities ---
    def list_opportunities(self, project_id: str) -> List[Opportunity]: ...
    def create_opportunity(
        self,
        project_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = None,
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
    ) -> Opportunity: ...

    def update_opportunity(
        self,
        project_id: str,
        opportunity_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = None,
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
        base_version: int | None = None,
    ) -> Opportunity: ...

    # --- Members / roles ---
    def list_members(self, project_id: str) -> List[Member]: ...
    def add_member(self, project_id: str, *, user_email: str, role: str) -> None: ...
    def remove_member(self, project_id: str, *, member_user_id: str) -> None: ...

    # --- Actions ---
    def list_actions(self, project_id: str) -> List[Action]: ...
    def create_action(
        self,
        project_id: str,
        *,
        target_type: str,  # "risk" | "opportunity"
        target_id: str,
        kind: str,  # mitigation|contingency|exploit
        title: str,
        description: str,
        status: str,  # open|doing|done
        owner_user_id: str | None,
    ) -> Action: ...

    def update_action(
        self,
        project_id: str,
        action_id: str,
        *,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
        base_version: int | None = None,
    ) -> Action: ...

    # --- Assessments ---
    def list_assessments(self, project_id: str, risk_id: str) -> List[Assessment]: ...
    def upsert_my_assessment(
        self,
        project_id: str,
        risk_id: str,
        probability: int,
        impact: int,
        notes: Optional[str] = None,
    ) -> Assessment: ...

    # optional but useful for “my row” highlight / prefill
    def current_user_id(self) -> Optional[str]: ...

    def create_snapshot(self, project_id: str) -> Dict[str, Any]: ...

    def top_history(
        self,
        project_id: str,
        *,
        kind: str = "risks",
        limit: int = 10,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ) -> List[Dict[str, Any]]: ...
