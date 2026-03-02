from __future__ import annotations

from fastapi import APIRouter

from ...db import Assessment, Item
from ...schemas import (
    OpportunityCreate,
    OpportunityOut,
    OpportunityUpdate,
    RiskAssessmentOut,
    RiskCreate,
    RiskOut,
    RiskUpdate,
)
from .crud_factory import create_crud_router

router = APIRouter()

router.include_router(
    create_crud_router(
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
)

router.include_router(
    create_crud_router(
        prefix="opportunities",
        tags=["opportunities"],
        Model=Item,
        CreateSchema=OpportunityCreate,
        UpdateSchema=OpportunityUpdate,
        OutSchema=OpportunityOut,
        fixed_type="opportunity",
    )
)
