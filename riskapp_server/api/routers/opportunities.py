from __future__ import annotations

from ...db import Opportunity, OpportunityAssessment
from ...schemas import (
    OpportunityAssessmentOut,
    OpportunityCreate,
    OpportunityOut,
    OpportunityUpdate,
)
from .crud_factory import create_crud_router

router = create_crud_router(
    prefix="opportunities",
    tags=["opportunities"],
    Model=Opportunity,
    CreateSchema=OpportunityCreate,
    UpdateSchema=OpportunityUpdate,
    OutSchema=OpportunityOut,
    AssessmentModel=OpportunityAssessment,
    AssessmentOutSchema=OpportunityAssessmentOut
)
