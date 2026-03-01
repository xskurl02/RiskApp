"""Small normalization helpers.

The client works with user-entered data (Qt forms) and server-provided JSON.
Normalizing optional text fields in one place prevents drift between:

- UI payloads
- SQLite rows
- API JSON

This module is intentionally tiny and dependency-free.
"""

from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from typing import Any


def norm_optional_text_fields(payload: MutableMapping[str, Any], keys: Iterable[str]) -> None:
    """Strip optional text values and convert empty strings to None in-place."""
    if not payload:
        return
    for k in keys:
        if k not in payload:
            continue
        v = payload.get(k)
        if v is None:
            continue
        s = str(v).strip()
        payload[k] = s if s else None