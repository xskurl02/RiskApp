"""Scoring utilities shared across endpoints and sync."""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException


def compute_score(probability: int, impact: int) -> int:
    return int(probability) * int(impact)


def compute_overall_impact(
    fallback: int,
    *,
    impact_cost: int | None = None,
    impact_time: int | None = None,
    impact_scope: int | None = None,
    impact_quality: int | None = None,
) -> int:
    """Compute overall impact as max of provided dimensions, or fallback."""
    dims: list[int] = []
    for v in (impact_cost, impact_time, impact_scope, impact_quality):
        if v is not None:
            dims.append(int(v))
    return max(dims) if dims else int(fallback)


def ensure_int_range(value: object, *, field: str, lo: int, hi: int) -> int:
    try:
        i = int(value)  # type: ignore[arg-type]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be int") from exc
    if i < lo or i > hi:
        raise HTTPException(status_code=400, detail=f"{field} must be in [{lo}..{hi}]")
    return i


def ensure_int_1_5(value: object, field: str) -> int:
    return ensure_int_range(value, field=field, lo=1, hi=5)


def overall_impact_from_record(record: dict, fallback: int) -> int:
    dims: list[int] = []
    for key in ("impact_cost", "impact_time", "impact_scope", "impact_quality"):
        if record.get(key) is not None:
            dims.append(ensure_int_1_5(record.get(key), key))
    if dims:
        return max(dims)
    return ensure_int_1_5(record.get("impact", fallback), "impact")
