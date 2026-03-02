"""Action target helpers.

The DB/API represent an action's target as an XOR pair: (risk_id, opportunity_id).
Internally, the server often needs a normalized representation to avoid branching.
"""

from __future__ import annotations

import uuid
from typing import Literal


ActionTargetType = Literal["risk", "opportunity"]


def combine_action_target_ids(
    *,
    risk_id: uuid.UUID | None,
    opportunity_id: uuid.UUID | None,
) -> tuple[ActionTargetType, uuid.UUID]:
    """Convert (risk_id, opportunity_id) to a normalized (target_type, target_id)."""
    if (risk_id is None) == (opportunity_id is None):
        raise ValueError("Action must target exactly one of risk_id/opportunity_id")
    if risk_id is not None:
        return "risk", risk_id
    return "opportunity", opportunity_id  # type: ignore[return-value]
