"""Shared field definitions for scored entities (Risk, Opportunity).

Put this file next to `models.py` (i.e., in the same package as
`riskapp_client.domain.models`) so it can be imported as:

    from riskapp_client.domain.scored_fields import ...
"""

from __future__ import annotations

from typing import Final


# Canonical list of optional/meta fields shared by Risk + Opportunity.
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


# SQLite column definitions for schema upgrades (order matters for stable diffs).
SCORED_ENTITY_META_SQLITE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("code", "TEXT"),
    ("description", "TEXT"),
    ("category", "TEXT"),
    ("threat", "TEXT"),
    ("triggers", "TEXT"),
    ("owner_user_id", "TEXT"),
    ("status", "TEXT"),
    ("identified_at", "TEXT"),
    ("status_changed_at", "TEXT"),
    ("response_at", "TEXT"),
    ("occurred_at", "TEXT"),
    ("mitigation_plan", "TEXT"),
    ("document_url", "TEXT"),
    ("impact_cost", "INTEGER"),
    ("impact_time", "INTEGER"),
    ("impact_scope", "INTEGER"),
    ("impact_quality", "INTEGER"),
)


# Allowed fields to persist into outbox entries (used for both risk + opportunity).
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


# Canonical CSV column ordering for export (used for both risk + opportunity).
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
