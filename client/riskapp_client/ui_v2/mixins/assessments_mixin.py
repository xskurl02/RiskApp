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
        item_id = getattr(self, "current_assessment_item_id", None)
        item_type = getattr(self, "current_assessment_item_type", "risk")

        # Update header label (best-effort title lookup).
        try:
            title = ""
            if item_id and item_type == "risk":
                title = (getattr(self, "_risk_title_by_id", {}) or {}).get(item_id, "")
            elif item_id and item_type == "opportunity":
                title = (getattr(self, "_opp_title_by_id", {}) or {}).get(item_id, "")
            nice = "Risk" if item_type == "risk" else "Opportunity"
            tab.target_label.setText(
                f"Target: {nice}{(' · ' + title) if title else ''}"
                if item_id
                else "Target: (none)"
            )
        except Exception:
            pass

        tab.assessments_table.setRowCount(0)

        if not pid or not item_id:
            tab.assess_p.setValue(3)
            tab.assess_i.setValue(3)
            tab.assess_notes.setText("")
            return

        assessments = self._call_backend(
            "Backend error", self.backend.list_assessments, pid, item_type, item_id
        )
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
            tab.assessments_table.setItem(
                row, 1, self._mk_item(str(a.probability), align_center=True)
            )
            tab.assessments_table.setItem(
                row, 2, self._mk_item(str(a.impact), align_center=True)
            )
            tab.assessments_table.setItem(
                row, 3, self._mk_item(str(a.score), align_center=True)
            )
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
        item_id = getattr(self, "current_assessment_item_id", None)
        item_type = getattr(self, "current_assessment_item_type", "risk")
        if not pid or not item_id:
            return

        p = int(tab.assess_p.value())
        i = int(tab.assess_i.value())
        notes = (tab.assess_notes.text() or "").strip()
        if (
            self._call_backend(
                "Assessment save failed",
                self.backend.upsert_my_assessment,
                pid,
                item_type,
                item_id,
                p,
                i,
                notes,
            )
            is None
        ):
            return

        self._refresh_assessments()
        self._update_sync_status()
