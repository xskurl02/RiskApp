from __future__ import annotations

from .crud_factory import create_crud_router
from ...db import Opportunity, OpportunityAssessment
from ...schemas import OpportunityCreate, OpportunityOut, OpportunityUpdate, OpportunityAssessmentOut

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
