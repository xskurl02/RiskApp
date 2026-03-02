from __future__ import annotations

from ...db import Risk, RiskAssessment
from ...schemas import RiskAssessmentOut, RiskCreate, RiskOut, RiskUpdate
from .crud_factory import create_crud_router

router = create_crud_router(
    prefix="risks",
    tags=["risks"],
    Model=Risk,
    CreateSchema=RiskCreate,
    UpdateSchema=RiskUpdate,
    OutSchema=RiskOut,
    AssessmentModel=RiskAssessment,
    AssessmentOutSchema=RiskAssessmentOut,
)
