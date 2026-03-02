from __future__ import annotations
from .crud_factory import create_crud_router
from ...db import Risk, RiskAssessment
from ...schemas import RiskCreate, RiskOut, RiskUpdate, RiskAssessmentOut

router = create_crud_router(
    prefix="risks",
    tags=["risks"],
    Model=Risk,
    CreateSchema=RiskCreate,
    UpdateSchema=RiskUpdate,
    OutSchema=RiskOut,
    AssessmentModel=RiskAssessment,
    AssessmentOutSchema=RiskAssessmentOut
)