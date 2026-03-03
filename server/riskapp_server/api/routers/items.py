"""Composite router.

This module is intentionally *thin* and only composes the more specific
`risks.py` and `opportunities.py` routers.

Why?
- Avoid duplicated CRUD-factory configuration in multiple places.
- Keep the FastAPI app wiring simple: include a single router for all items.

Note: Do not include BOTH this router and the individual `risks.py` and
`opportunities.py` routers in the same FastAPI app, otherwise you will register
duplicate routes.
"""

from __future__ import annotations

from fastapi import APIRouter

from riskapp_server.api.routers.opportunities import router as opportunities_router
from riskapp_server.api.routers.risks import router as risks_router

router = APIRouter()
router.include_router(risks_router)
router.include_router(opportunities_router)
