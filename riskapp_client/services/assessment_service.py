"""Assessment operations for offline-first mode."""

from __future__ import annotations

import uuid
from typing import Optional

from riskapp_client.adapters.local.outbox import OutboxStore
from riskapp_client.adapters.local.sqlite_store import LocalStore, utc_iso
from riskapp_client.domain.models import Assessment


class AssessmentService:
    """Create/update my assessment locally and queue sync."""

    def __init__(self, store: LocalStore, outbox: OutboxStore) -> None:
        self._store = store
        self._outbox = outbox

    def list(self, project_id: str, risk_id: str) -> list[Assessment]:
        return self._store.list_assessments(project_id, risk_id)

    def upsert_my(
        self,
        project_id: str,
        risk_id: str,
        assessor_user_id: str,
        probability: int,
        impact: int,
        notes: Optional[str] = None,
    ) -> Assessment:
        assessment_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"assessment:{risk_id}:{assessor_user_id}"))
        updated_at = utc_iso()

        try:
            _, version = self._store.get_assessment_project_and_version(assessment_id)
        except Exception:  # noqa: BLE001
            version = 0

        self._store.upsert_local_assessment(
            assessment_id=assessment_id,
            project_id=project_id,
            risk_id=risk_id,
            assessor_user_id=assessor_user_id,
            probability=int(probability),
            impact=int(impact),
            notes=notes or "",
            version=version,
            is_deleted=False,
            updated_at=updated_at,
            dirty=1,
        )
        self._outbox.queue_assessment_upsert(
            assessment_id,
            project_id,
            risk_id,
            assessor_user_id,
            int(probability),
            int(impact),
            notes,
        )

        return Assessment(
            id=assessment_id,
            risk_id=risk_id,
            assessor_user_id=assessor_user_id,
            probability=int(probability),
            impact=int(impact),
            notes=notes or "",
            updated_at=updated_at,
            version=version,
            is_deleted=False,
        )
