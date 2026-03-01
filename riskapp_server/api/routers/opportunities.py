from __future__ import annotations

from api.routers.crud_factory import create_crud_router
from db import Opportunity
from schemas import OpportunityCreate, OpportunityOut, OpportunityUpdate

router = create_crud_router(
    prefix="opportunities",
    tags=["opportunities"],
    Model=Opportunity,
    CreateSchema=OpportunityCreate,
    UpdateSchema=OpportunityUpdate,
    OutSchema=OpportunityOut,
)
