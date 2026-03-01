"""Filtering helpers for risks and opportunities (client-side)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Protocol, TypeVar

from riskapp_client.domain.domain_models import Opportunity, Risk


def parse_date(value: str) -> datetime | None:
    """Parse YYYY-MM-DD or ISO datetime; return None if invalid."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return datetime.fromisoformat(text + "T00:00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None

ANY_STATUS = "(any)"
MAX_SCORE = 999_999

# Backwards-compat alias for older internal callsites
_parse_date = parse_date


@dataclass(frozen=True)
class ScoredFilterCriteria:
    """Shared filter criteria for any scored entity."""

    search: str = ""
    min_score: int = 0
    max_score: int = MAX_SCORE
    status: str = ANY_STATUS
    category_contains: str = ""
    owner_contains: str = ""
    identified_from: datetime | None = None
    identified_to: datetime | None = None

# Backward-compatible names
RiskFilterCriteria = ScoredFilterCriteria
OpportunityFilterCriteria = ScoredFilterCriteria

class _Scored(Protocol):
    title: str | None
    code: str | None
    category: str | None
    description: str | None
    score: int
    status: str | None
    owner_user_id: str | None
    identified_at: str | None


TScored = TypeVar("TScored", bound=_Scored)


def filter_scored(items: List[TScored], criteria: ScoredFilterCriteria) -> List[TScored]:
    """Filter any scored entity according to UI criteria."""
    s = (criteria.search or "").strip().lower()

    mn = int(criteria.min_score)
    mx = int(criteria.max_score)
    if mn > mx:
        mn, mx = mx, mn

    st = (criteria.status or ANY_STATUS).strip().lower()
    cat = (criteria.category_contains or "").strip().lower()
    owner = (criteria.owner_contains or "").strip().lower()

    dt_from = criteria.identified_from
    dt_to = criteria.identified_to

    out: List[TScored] = []

    for it in items:
        hay = " ".join(
            [
                getattr(it, "title", "") or "",
                getattr(it, "code", "") or "",
                getattr(it, "category", "") or "",
                getattr(it, "description", "") or "",
            ]
        ).lower()
        if s and s not in hay:
            continue
        if it.score < mn or it.score > mx:
            continue
        if st != ANY_STATUS and (it.status or "").strip().lower() != st:
            continue
        if cat and cat not in (it.category or "").lower():
            continue
        if owner and owner not in (it.owner_user_id or "").lower():
            continue

        if dt_from or dt_to:
            dt = parse_date(it.identified_at or "")
            if not dt:
                continue
            if dt_from and dt < dt_from:
                continue
            if dt_to and dt > dt_to:
                continue

        out.append(it)
    return out

def filter_risks(risks: List[Risk], criteria: RiskFilterCriteria) -> List[Risk]:
    return filter_scored(risks, criteria)

def filter_opportunities(opps: List[Opportunity], criteria: OpportunityFilterCriteria) -> List[Opportunity]:
    return filter_scored(opps, criteria)