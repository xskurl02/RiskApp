"""Shared field definitions for scored entities (Risk, Opportunity).

These entities share the same "meta" payload surface across the client:

- Local write services (RiskService/OpportunityService)
- Outbox squashing/allowed-field filtering
- ApiBackend request body serialization
- CSV export column ordering

Keeping the canonical lists here prevents drift.
"""

from __future__ import annotations

from typing import Final


SCORED_ENTITY_META_KEYS: Final[tuple[str, ...]] = (
    "code",
    "description",
    "category",
    "threat",
    "triggers",
    "mitigation_plan",
    "document_url",
    "owner_user_id",
    "status",
    "identified_at",
    "status_changed_at",
    "response_at",
    "occurred_at",
    "impact_cost",
    "impact_time",
    "impact_scope",
    "impact_quality",
)


SCORED_ENTITY_OUTBOX_ALLOWED_KEYS: Final[frozenset[str]] = frozenset(
    (
        "id",
        "title",
        "probability",
        "impact",
        *SCORED_ENTITY_META_KEYS,
        "is_deleted",
        "created_at",
        "created_by",
    )
)


SCORED_ENTITY_CSV_COLUMNS: Final[tuple[str, ...]] = (
    "code",
    "title",
    "category",
    "status",
    "owner_user_id",
    "probability",
    "impact",
    "score",
    "identified_at",
    "response_at",
    "occurred_at",
    "description",
    "threat",
    "triggers",
)
