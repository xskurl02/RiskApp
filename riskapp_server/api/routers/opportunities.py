from __future__ import annotations

from ...db import Item
from ...schemas import OpportunityCreate, OpportunityOut, OpportunityUpdate
from .crud_factory import create_crud_router

router = create_crud_router(
    prefix="opportunities",
    tags=["opportunities"],
    Model=Item,
    CreateSchema=OpportunityCreate,
    UpdateSchema=OpportunityUpdate,
    OutSchema=OpportunityOut,
    fixed_type="opportunity",
)
