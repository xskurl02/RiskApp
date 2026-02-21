"""MainWindow mixin for the Assessments tab.

Lists assessments for the currently selected risk and lets the user upsert their own.
"""
from __future__ import annotations

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

from riskapp_client.domain.models import Assessment

class AssessmentsMixin:
    """MainWindow mixin: AssessmentsMixin"""
    def _refresh_assessments(self) -> None:
        pid = self.current_project_id
        rid = self.current_risk_id

        self.assessments_table.setRowCount(0)

        if not pid or not rid:
            # no selection => clear editor
            self.assess_p.setValue(3)
            self.assess_i.setValue(3)
            self.assess_notes.setText("")
            return

        try:
            assessments: list[Assessment] = self.backend.list_assessments(pid, rid)
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))
            return

        my_uid = None
        if hasattr(self.backend, "current_user_id"):
            try:
                my_uid = self.backend.current_user_id()  # type: ignore[attr-defined]
            except Exception:
                my_uid = None

        # fill table
        my_row: Assessment | None = None
        for a in assessments:
            row = self.assessments_table.rowCount()
            self.assessments_table.insertRow(row)

            assessor = a.assessor_user_id or ""
            assessor_short = assessor[:8] if assessor else ""

            self.assessments_table.setItem(row, 0, QTableWidgetItem(assessor_short))
            self.assessments_table.setItem(row, 1, QTableWidgetItem(str(a.probability)))
            self.assessments_table.setItem(row, 2, QTableWidgetItem(str(a.impact)))
            self.assessments_table.setItem(row, 3, QTableWidgetItem(str(a.score)))
            self.assessments_table.setItem(row, 4, QTableWidgetItem(a.notes or ""))
            self.assessments_table.setItem(row, 5, QTableWidgetItem(a.updated_at or ""))

            for c in (1, 2, 3):
                it = self.assessments_table.item(row, c)
                if it:
                    it.setTextAlignment(Qt.AlignCenter)

            if my_uid and assessor == my_uid:
                my_row = a

        self.assessments_table.resizeColumnsToContents()

        # prefill “my assessment” editor if present
        if my_row:
            self.assess_p.setValue(int(my_row.probability))
            self.assess_i.setValue(int(my_row.impact))
            self.assess_notes.setText(my_row.notes or "")
        else:
            # if no personal assessment, reset editor
            self.assess_p.setValue(3)
            self.assess_i.setValue(3)
            self.assess_notes.setText("")

    def _save_assessment(self) -> None:
        pid = self.current_project_id
        rid = self.current_risk_id
        if not pid or not rid:
            return

        p = int(self.assess_p.value())
        i = int(self.assess_i.value())
        notes = (self.assess_notes.text() or "").strip()

        try:
            self.backend.upsert_my_assessment(pid, rid, p, i, notes)
        except Exception as e:
            QMessageBox.critical(self, "Assessment save failed", str(e))
            return

        self._refresh_assessments()
        self._update_sync_status()
