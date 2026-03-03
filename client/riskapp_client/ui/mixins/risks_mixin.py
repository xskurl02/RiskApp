"""MainWindow mixin for the Risks tab.

Filtering, table rendering, editor behavior, column sizing, and CSV export for risks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module

# NOTE:
# - CSV export lives under adapters/local_storage.
# - Client-side filtering lives in services/entity_filters.
from riskapp_client.adapters.local_storage import csv_data_exporter as export_csv
from riskapp_client.services import entity_filters as filters
from riskapp_client.ui.mixins.scored_entity_mixin import ScoredEntityMixin


class RisksMixin(ScoredEntityMixin):
    """MainWindow mixin: RisksMixin"""

    def _export_risks_csv(self) -> None:
        self._export_entity_csv("risks.csv", self._risk_cache, export_csv.export_risks)

    def _ensure_risks_column_widths(self, pid: str) -> None:
        """Restore cached per-project column widths or autosize once per project switch."""
        if pid == self._risks_last_pid:
            return

        if pid in self._risks_col_widths:
            for c, w in enumerate(self._risks_col_widths[pid]):
                self.risks_table.setColumnWidth(c, w)
        else:
            self._autosize_risks_columns_like_excel()
            self._risks_col_widths[pid] = [
                self.risks_table.columnWidth(c)
                for c in range(self.risks_table.columnCount())
            ]

        self._risks_last_pid = pid

    def _refresh_risks(self, select_risk_id: str | None = None) -> None:
        pid = self.current_project_id
        if not pid:
            return
        filters_dict = {
            "min_score": self.filter_min_score,
            "max_score": self.filter_max_score,
            "search": self.filter_search,
            "status": self.filter_status,
            "category": self.filter_category,
            "owner": self.filter_owner,
            "from_date": self.filter_from,
            "to_date": self.filter_to,
        }
        res = self._refresh_entity(
            pid,
            self.backend.list_risks,
            filters.filter_risks,
            filters.RiskFilterCriteria,
            self.filter_report,
            self.risks_table,
            filters_dict,
            self._mk_item,
            getattr(self.backend, "risks_report", None),
            select_risk_id,
        )
        if res is not None:
            self._risk_cache = res
        # Column sizing / per-project caching and final card fit
        self._ensure_risks_column_widths(pid)
        self._fit_table_card()

    def _autosize_risks_columns_like_excel(self) -> None:
        hh = self.risks_table.horizontalHeader()
        self.risks_table.resizeColumnsToContents()
        for c in range(self.risks_table.columnCount()):
            w = max(self.risks_table.columnWidth(c), hh.sectionSizeHint(c))
            self.risks_table.setColumnWidth(c, w)

    def _maybe_expand_title_column(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        hh = self.risks_table.horizontalHeader()

        # Title is column 1 (Code, Title, ...)
        title_col = 1
        old = self.risks_table.columnWidth(title_col)
        self.risks_table.resizeColumnToContents(title_col)
        contents = self.risks_table.columnWidth(title_col)

        needed = max(old, contents, hh.sectionSizeHint(title_col))
        if needed != self.risks_table.columnWidth(title_col):
            self.risks_table.setColumnWidth(title_col, needed)

        self._risks_col_widths[pid] = [
            self.risks_table.columnWidth(c)
            for c in range(self.risks_table.columnCount())
        ]
        self._fit_table_card()

    def _on_risk_clicked(self, row: int, col: int) -> None:
        new_id = self._on_entity_clicked(
            row,
            col,
            self.risks_table,
            self._risk_cache,
            self.current_risk_id,
            self._editor_dirty,
            self._commit_editor_changes,
            self.risk_form,
            self.editor_label,
            "Editor",
        )
        if new_id:
            self.current_risk_id = new_id
            self._editor_dirty = False
            self.current_assessment_item_type = "risk"
            self.current_assessment_item_id = new_id
            self._refresh_assessments()

    def _fit_table_card(self, max_height: int = 260) -> None:
        if not hasattr(self, "_table_card"):
            return

        self.risks_table.resizeRowsToContents()

        hh = self.risks_table.horizontalHeader()
        hh.setStyleSheet("""
            QHeaderView::section {
                background: white;
                border: none;
                border-bottom: 1px solid #d0d0d0;
                padding: 4px 6px;
            }
            """)
        vh = self.risks_table.verticalHeader()

        border_px = 2
        w = hh.length() + border_px
        h = hh.height() + vh.length() + border_px

        if h > max_height:
            h = max_height
            self.risks_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            w += self.risks_table.verticalScrollBar().sizeHint().width()
        else:
            self.risks_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.risks_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.risks_table.setFixedSize(w, h)

        self._table_card.setMinimumHeight(0)
        self._table_card.setMaximumHeight(16777215)

    def _mark_editor_dirty(self, *args) -> None:
        self._editor_dirty = True

    def _commit_editor_changes(
        self, *, refresh: bool, select_risk_id: str | None = None
    ) -> None:
        def ref_cb(select_id):
            self._refresh_risks(select_id)
            self._refresh_matrix()
            self._maybe_expand_title_column()

        if self._commit_entity_editor_changes(
            self.current_risk_id,
            self._editor_dirty,
            self.risk_form,
            self.backend.update_risk,
            ref_cb if refresh else None,
            select_risk_id,
        ):
            self._editor_dirty = False

    def _start_new_risk(self) -> None:
        self._commit_editor_changes(refresh=True)

        self.current_risk_id = None
        self.current_assessment_item_id = None
        self.current_assessment_item_type = "risk"
        self.editor_label.setText("Editor (new risk)")
        self.risk_form.set_values(title="", probability=3, impact=3)
        self._editor_dirty = False

        self.risks_table.clearSelection()
        self.risks_table.setCurrentItem(None)
        self._refresh_assessments()

    def _save_risk(self, payload: dict) -> None:
        extra = [
            self._refresh_action_risk_combo,
            self._refresh_actions,
            self._refresh_matrix,
        ]
        saved_id = self._save_entity(
            payload,
            self.current_risk_id,
            self.backend.update_risk,
            self.backend.create_risk,
            self._refresh_risks,
            self.risk_form,
            self.editor_label,
            "Editor",
            extra,
        )
        if saved_id:
            self.current_risk_id = saved_id
            self._editor_dirty = False
            self.current_assessment_item_type = "risk"
            self.current_assessment_item_id = saved_id
            self._refresh_assessments()
