"""Filtering helpers for risks and opportunities (client-side)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from riskapp_client.domain.models import Opportunity, Risk


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

# Backwards-compat alias for older internal callsites
_parse_date = parse_date

@dataclass(frozen=True)
class RiskFilterCriteria:
    search: str = ""
    min_score: int = 0
    max_score: int = 999999
    status: str = "(any)"
    category_contains: str = ""
    owner_contains: str = ""
    identified_from: datetime | None = None
    identified_to: datetime | None = None


@dataclass(frozen=True)
class OpportunityFilterCriteria:
    search: str = ""
    min_score: int = 0
    max_score: int = 999999
    status: str = "(any)"
    category_contains: str = ""
    owner_contains: str = ""
    identified_from: datetime | None = None
    identified_to: datetime | None = None


def filter_risks(risks: List[Risk], criteria: RiskFilterCriteria) -> List[Risk]:
    """Filter risks according to UI criteria."""
    s = (criteria.search or "").strip().lower()

    mn = int(criteria.min_score)
    mx = int(criteria.max_score)
    if mn > mx:
        mn, mx = mx, mn

    st = (criteria.status or "(any)").strip().lower()
    cat = (criteria.category_contains or "").strip().lower()
    owner = (criteria.owner_contains or "").strip().lower()

    dt_from = criteria.identified_from
    dt_to = criteria.identified_to

    out: List[Risk] = []
    for r in risks:
        hay = " ".join([r.title or "", r.code or "", r.category or "", r.description or ""]).lower()
        if s and s not in hay:
            continue
        if r.score < mn or r.score > mx:
            continue
        if st != "(any)" and (r.status or "").strip().lower() != st:
            continue
        if cat and cat not in (r.category or "").lower():
            continue
        if owner and owner not in (r.owner_user_id or "").lower():
            continue

        if dt_from or dt_to:
            rid_dt = parse_date(r.identified_at or "")
            if not rid_dt:
                continue
            if dt_from and rid_dt < dt_from:
                continue
            if dt_to and rid_dt > dt_to:
                continue

        out.append(r)
    return out


def filter_opportunities(opps: List[Opportunity], criteria: OpportunityFilterCriteria) -> List[Opportunity]:
    """Filter opportunities according to UI criteria."""
    s = (criteria.search or "").strip().lower()

    mn = int(criteria.min_score)
    mx = int(criteria.max_score)
    if mn > mx:
        mn, mx = mx, mn

    st = (criteria.status or "(any)").strip().lower()
    cat = (criteria.category_contains or "").strip().lower()
    owner = (criteria.owner_contains or "").strip().lower()

    dt_from = criteria.identified_from
    dt_to = criteria.identified_to

    out: List[Opportunity] = []
    for o in opps:
        hay = " ".join([o.title or "", o.code or "", o.category or "", o.description or ""]).lower()
        if s and s not in hay:
            continue
        if o.score < mn or o.score > mx:
            continue
        if st != "(any)" and (o.status or "").strip().lower() != st:
            continue
        if cat and cat not in (o.category or "").lower():
            continue
        if owner and owner not in (o.owner_user_id or "").lower():
            continue
        if dt_from or dt_to:
            oid_dt = parse_date(o.identified_at or "")
            if not oid_dt:
                continue
            if dt_from and oid_dt < dt_from:
                continue
            if dt_to and oid_dt > dt_to:
                continue

        out.append(o)
    return out