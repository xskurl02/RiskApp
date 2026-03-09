"""Small normalization helpers.

The client works with user-entered data (Qt forms) and server-provided JSON.
Normalizing optional text fields in one place prevents drift between:

- UI payloads
- SQLite rows
- API JSON

"""

from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from typing import Any


def norm_optional_text_fields(
    payload: MutableMapping[str, Any], keys: Iterable[str]
) -> None:
    """Strip optional text values and convert empty strings to None in-place.

    Only keys provided in `keys` are touched. Values are coerced to `str` and
    stripped; if the result is empty it becomes None.
    """
    if not payload:
        return
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        payload[key] = normalized if normalized else None
