"""Client-side domain models.

These models intentionally avoid framework-specific types (e.g., Pydantic/ORM)
so they can be reused by:
- the online API client,
- the offline SQLite cache/sync engine,
- tests and tooling (CSV export/import, snapshots).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from riskapp_client.domain.scored_entity_fields import (
    ACTION_DEFAULT_STATUS,
    DEFAULT_STATUS,
)


def _int_or_none(value: Any) -> int | None:
    """Best-effort int conversion for optional fields.

    This is intentionally permissive because optional impact dimensions are
    commonly stored as NULL/"" during editing or sync.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class Member:
    """Represent Member."""

    user_id: str
    email: str
    role: str
    created_at: str | None = None


@dataclass
class Project:
    """Represent Project."""

    id: str
    name: str
    description: str = ""


@dataclass
class Action:
    """Represent Action."""

    id: str
    project_id: str

    # Exactly one of these should be set (kept as two fields for backward
    # compatibility with existing API payloads).
    risk_id: str | None
    opportunity_id: str | None

    # mitigation|contingency|exploit
    kind: str
    title: str
    description: str = ""
    status: str = ACTION_DEFAULT_STATUS  # open|doing|done
    owner_user_id: str | None = None

    # sync metadata
    version: int = 0
    is_deleted: bool = False
    updated_at: str = ""


@dataclass
class ScoredEntity:
    """Base type for items shown in the risk/opportunity matrix.

    `score` is derived as probability * impact.

    If per-dimension impacts (cost/time/scope/quality) are provided, `impact`
    becomes their max, which keeps the scalar score consistent with the most
    severe dimension.
    """

    id: str
    project_id: str

    # Required / assignment fields
    code: str | None = None  # human-facing unique identifier (search/filter)
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
    # 1..5 scale (qualitative labels live in UI/back-end enums)
    probability: int = 3
    impact: int = 3
    # Optional per-dimension impacts (also 1..5). When present, scalar impact is
    # derived as max().
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
        """Recompute derived fields after initialization."""
        if self.status is None:
            self.status = DEFAULT_STATUS

        dims = (
            _int_or_none(self.impact_cost),
            _int_or_none(self.impact_time),
            _int_or_none(self.impact_scope),
            _int_or_none(self.impact_quality),
        )
        dims_int = [x for x in dims if x is not None]
        if dims_int:
            self.impact = max(dims_int)

        # Keep probability/impact strict: invalid values should be caught early.
        self.score = int(self.probability) * int(self.impact)


@dataclass
class Risk(ScoredEntity):
    """Represent Risk."""

    pass


@dataclass
class Opportunity(ScoredEntity):
    """Represent Opportunity."""

    pass


@dataclass
class Assessment:
    """Represent Assessment."""

    id: str
    item_id: str
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
        """Recompute derived fields after initialization."""
        self.score = int(self.probability) * int(self.impact)

    # Backward-compatible aliases (risk-only older code paths).
    @property
    def risk_id(self) -> str:
        """Handle risk id."""
        return self.item_id

    @property
    def opportunity_id(self) -> str:
        """Handle opportunity id."""
        return self.item_id


class Backend(Protocol):
    """Protocol describing the backend contract used by the client."""

    def list_projects(self) -> list[Project]:
        """Return projects."""
        ...

    # --- Risks ---
    def list_risks(self, project_id: str) -> list[Risk]:
        """Return risks."""
        ...

    def risks_report(self, project_id: str, **filters) -> dict:
        """Handle risks report."""
        ...

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
    ) -> Risk:
        """Create risk."""
        ...

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
    ) -> Risk:
        """Update risk."""
        ...

    def delete_risk(self, project_id: str, risk_id: str) -> None:
        """Delete risk."""
        ...

    # --- Opportunities ---
    def list_opportunities(self, project_id: str) -> list[Opportunity]:
        """Return opportunities."""
        ...

    def opportunities_report(self, project_id: str, **filters) -> dict:
        """Handle opportunities report."""
        ...

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
    ) -> Opportunity:
        """Create opportunity."""
        ...

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
    ) -> Opportunity:
        """Update opportunity."""
        ...

    def delete_opportunity(self, project_id: str, opportunity_id: str) -> None:
        """Delete opportunity."""
        ...

    # --- Members / roles ---
    def list_members(self, project_id: str) -> list[Member]:
        """Return members."""
        ...

    def add_member(self, project_id: str, *, user_email: str, role: str) -> None:
        """Add member."""
        ...

    def remove_member(self, project_id: str, *, member_user_id: str) -> None:
        """Remove member."""
        ...

    # --- Actions ---
    def list_actions(self, project_id: str) -> list[Action]:
        """Return actions."""
        ...

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
    ) -> Action:
        """Create action."""
        ...

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
    ) -> Action:
        """Update action."""
        ...

    # --- Assessments ---
    def list_assessments(
        self, project_id: str, item_type: str, item_id: str
    ) -> list[Assessment]:
        """Return assessments."""
        ...

    def upsert_my_assessment(
        self,
        project_id: str,
        item_type: str,
        item_id: str,
        probability: int,
        impact: int,
        notes: str | None = None,
    ) -> Assessment:
        """Insert or update my assessment."""
        ...

    # optional but useful for “my row” highlight / prefill
    def current_user_id(self) -> str | None:
        """Handle current user id."""
        ...

    def create_snapshot(self, project_id: str) -> dict[str, Any]:
        """Create snapshot."""
        ...

    def top_history(
        self,
        project_id: str,
        *,
        kind: str = "risks",
        limit: int = 10,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ) -> list[dict[str, Any]]:
        """Handle top history."""
        ...
