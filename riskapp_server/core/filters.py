"""Query/filter helpers for list/report endpoints."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.sql import Select


def csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def apply_date_range(
    stmt: Select,
    field,
    *,
    from_date: date | None,
    to_date: date | None,
) -> Select:
    if from_date is not None:
        start = datetime(from_date.year, from_date.month, from_date.day)
        stmt = stmt.where(field >= start)
    if to_date is not None:
        end_exclusive = datetime(to_date.year, to_date.month, to_date.day) + timedelta(
            days=1
        )
        stmt = stmt.where(field < end_exclusive)
    return stmt


def normalize_score_range(
    min_score: int | None,
    max_score: int | None,
) -> tuple[int | None, int | None]:
    if min_score is not None and max_score is not None and min_score > max_score:
        return max_score, min_score
    return min_score, max_score


def apply_item_filters(
    stmt: Select,
    Model,
    *,
    search: str | None,
    min_score: int | None,
    max_score: int | None,
    status: str | None,
    category: str | None,
    owner_user_id,
    from_date: date | None,
    to_date: date | None,
) -> Select:
    """Apply the common filters used by Risk and Opportunity list/report endpoints."""
    status_values = [s.lower() for s in csv_list(status)]
    include_deleted = "deleted" in status_values

    non_deleted_statuses = [s for s in status_values if s != "deleted"]

    if include_deleted:
        cond = Model.is_deleted.is_(True)
        if non_deleted_statuses:
            cond = or_(cond, Model.status.in_(non_deleted_statuses))
        stmt = stmt.where(cond)
    else:
        stmt = stmt.where(Model.is_deleted.is_(False))
        if non_deleted_statuses:
            stmt = stmt.where(Model.status.in_(non_deleted_statuses))

    if category and category.strip():
        cats = csv_list(category)
        if cats:
            stmt = stmt.where(or_(*[Model.category.ilike(f"%{c}%") for c in cats]))

    if owner_user_id is not None:
        stmt = stmt.where(Model.owner_user_id == owner_user_id)

    stmt = apply_date_range(stmt, Model.identified_at, from_date=from_date, to_date=to_date)

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Model.title.ilike(q), Model.code.ilike(q)))

    min_score, max_score = normalize_score_range(min_score, max_score)
    if min_score is not None:
        stmt = stmt.where(Model.score >= int(min_score))
    if max_score is not None:
        stmt = stmt.where(Model.score <= int(max_score))

    return stmt
