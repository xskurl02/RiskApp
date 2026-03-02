from __future__ import annotations

from ...db import Assessment, Item
from ...schemas import RiskAssessmentOut, RiskCreate, RiskOut, RiskUpdate
from .crud_factory import create_crud_router

router = create_crud_router(
    prefix="risks",
    tags=["risks"],
    Model=Item,
    CreateSchema=RiskCreate,
    UpdateSchema=RiskUpdate,
    OutSchema=RiskOut,
    fixed_type="risk",
    AssessmentModel=Assessment,
    AssessmentOutSchema=RiskAssessmentOut,
)
