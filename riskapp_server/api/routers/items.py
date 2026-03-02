from __future__ import annotations

from ...db import Assessment, Item
from ...schemas import AssessmentOut, ItemCreate, ItemOut, ItemUpdate
from .crud_factory import create_crud_router

router = create_crud_router(
    prefix="items",
    tags=["items"],
    Model=Item,
    CreateSchema=ItemCreate,
    UpdateSchema=ItemUpdate,
    OutSchema=ItemOut,
    AssessmentModel=Assessment,
    AssessmentOutSchema=AssessmentOut,
)
