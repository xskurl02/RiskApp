"""MainWindow mixin for the Assessments tab.

Lists assessments for the currently selected risk and lets the user upsert their own.
"""
from __future__ import annotations

from riskapp_client.domain.domain_models import Assessment


class AssessmentsMixin:
    """MainWindow mixin: AssessmentsMixin"""

    def _refresh_assessments(self) -> None:
        tab = self.assessments_tab
        pid = self.current_project_id
        rid = self.current_risk_id

        tab.assessments_table.setRowCount(0)

        if not pid or not rid:
            tab.assess_p.setValue(3)
            tab.assess_i.setValue(3)
            tab.assess_notes.setText("")
            return

        assessments = self._call_backend("Backend error", self.backend.list_assessments, pid, rid)
        if assessments is None:
            return

        my_uid = None
        if hasattr(self.backend, "current_user_id"):
            try:
                my_uid = self.backend.current_user_id()  # type: ignore[attr-defined]
            except Exception:
                my_uid = None

        my_row: Assessment | None = None
        for a in assessments:
            row = tab.assessments_table.rowCount()
            tab.assessments_table.insertRow(row)

            assessor = a.assessor_user_id or ""
            assessor_short = assessor[:8] if assessor else ""

            tab.assessments_table.setItem(row, 0, self._mk_item(assessor_short))
            tab.assessments_table.setItem(row, 1, self._mk_item(str(a.probability), align_center=True))
            tab.assessments_table.setItem(row, 2, self._mk_item(str(a.impact), align_center=True))
            tab.assessments_table.setItem(row, 3, self._mk_item(str(a.score), align_center=True))
            tab.assessments_table.setItem(row, 4, self._mk_item(a.notes or ""))
            tab.assessments_table.setItem(row, 5, self._mk_item(a.updated_at or ""))

            if my_uid and assessor == my_uid:
                my_row = a

        tab.assessments_table.resizeColumnsToContents()

        if my_row:
            tab.assess_p.setValue(int(my_row.probability))
            tab.assess_i.setValue(int(my_row.impact))
            tab.assess_notes.setText(my_row.notes or "")
        else:
            tab.assess_p.setValue(3)
            tab.assess_i.setValue(3)
            tab.assess_notes.setText("")

    def _save_assessment(self) -> None:
        tab = self.assessments_tab
        pid = self.current_project_id
        rid = self.current_risk_id
        if not pid or not rid:
            return

        p = int(tab.assess_p.value())
        i = int(tab.assess_i.value())
        notes = (tab.assess_notes.text() or "").strip()
        if self._call_backend("Assessment save failed", self.backend.upsert_my_assessment, pid, rid, p, i, notes) is None:
            return

        self._refresh_assessments()
        self._update_sync_status()
