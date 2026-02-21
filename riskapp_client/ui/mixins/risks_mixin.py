"""MainWindow mixin for the Risks tab.

Filtering, table rendering, editor behavior, column sizing, and CSV export for risks.
"""
from __future__ import annotations

from datetime import datetime
from collections import Counter

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

from riskapp_client.domain.models import Risk
from riskapp_client.services import export_csv, filters

class RisksMixin:
    """MainWindow mixin: RisksMixin"""
    def _export_risks_csv(self) -> None:
        if not self.current_project_id:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export risks CSV", "risks.csv", "CSV Files (*.csv)")
        if not path:
            return
        
        rows = list(self._risk_cache.values())
        rows.sort(key=lambda r: (r.score, r.title), reverse=True)
        export_csv.export_risks(path, rows)

    def _mk_item(
        self,
        text: str,
        *,
        entity_id: str | None = None,
        align_center: bool = False,
    ) -> QTableWidgetItem:
        """Create a table item with optional entity-id in Qt.UserRole."""
        item = QTableWidgetItem(text)
        if entity_id is not None:
            item.setData(Qt.UserRole, entity_id)
        if align_center:
            item.setTextAlignment(Qt.AlignCenter)
        return item


    def _select_row_by_entity_id(self, entity_id: str | None) -> None:
        """Select the row in risks_table whose column-0 Qt.UserRole matches entity_id."""
        if not entity_id:
            return
        target = str(entity_id)

        for row in range(self.risks_table.rowCount()):
            it = self.risks_table.item(row, 0)
            if it and str(it.data(Qt.UserRole)) == target:
                self.risks_table.selectRow(row)
                self.risks_table.setCurrentCell(row, 0)
                return


    def _update_risk_filter_report(self, full: list[Risk], filtered: list[Risk]) -> None:
        """Render the filter report label based on the displayed subset."""
        if not filtered:
            self.filter_report.setText(f"Showing 0/{len(full)}")
            return

        scores = [r.score for r in filtered]
        avg = sum(scores) / len(scores)

        status_counts = Counter((r.status or "concept") for r in filtered)
        order = ["active", "concept", "closed", "happened", "deleted"]
        status_bits = [f"{st} {status_counts[st]}" for st in order if status_counts.get(st)]
        for st, n in status_counts.most_common():
            if st not in order:
                status_bits.append(f"{st} {n}")

        cat_counts = Counter((r.category or "(none)") for r in filtered)
        top_cats = [f"{c} {n}" for c, n in cat_counts.most_common(3) if c and c != "(none)"]

        lines = [
            f"Showing {len(filtered)}/{len(full)} · score min {min(scores)} · max {max(scores)} · avg {avg:.1f}",
            f"Status: {', '.join(status_bits) if status_bits else '(none)'}",
        ]
        if top_cats:
            lines.append(f"Top categories: {', '.join(top_cats)}")

        self.filter_report.setText("<br>".join(lines))


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
                self.risks_table.columnWidth(c) for c in range(self.risks_table.columnCount())
            ]

        self._risks_last_pid = pid

    def _refresh_risks(self, select_risk_id: str | None = None) -> None:
        pid = self.current_project_id
        if not pid:
            return

        try:
            full = self.backend.list_risks(pid)
        except Exception as exc:
            QMessageBox.critical(self, "Backend error", str(exc))
            return

        filtered = self._apply_risk_filters(full)

        self._update_risk_filter_report(full, filtered)
        self._risk_cache = {r.id: r for r in filtered}

        # Populate table
        self.risks_table.setRowCount(len(filtered))
        for row, r in enumerate(filtered):
            self.risks_table.setItem(row, 0, self._mk_item(r.code or "", entity_id=r.id))
            self.risks_table.setItem(row, 1, self._mk_item(r.title, entity_id=r.id))
            self.risks_table.setItem(row, 2, self._mk_item(r.category or ""))
            self.risks_table.setItem(row, 3, self._mk_item(r.status or ""))
            self.risks_table.setItem(row, 4, self._mk_item(r.owner_user_id or ""))
            self.risks_table.setItem(row, 5, self._mk_item(str(r.probability), align_center=True))
            self.risks_table.setItem(row, 6, self._mk_item(str(r.impact), align_center=True))
            self.risks_table.setItem(row, 7, self._mk_item(str(r.score), align_center=True))

        self._select_row_by_entity_id(select_risk_id)

        # Column sizing / per-project caching and final card fit
        self._ensure_risks_column_widths(pid)
        self._fit_table_card()

    def _autosize_risks_columns_like_excel(self) -> None:
        hh = self.risks_table.horizontalHeader()
        self.risks_table.resizeColumnsToContents()
        for c in range(self.risks_table.columnCount()):
            w = max(self.risks_table.columnWidth(c), hh.sectionSizeHint(c))
            self.risks_table.setColumnWidth(c, w)

    def _apply_risk_filters(self, risks: list[Risk]) -> list[Risk]:
        mn = int(self.filter_min_score.value())
        mx = int(self.filter_max_score.value())
        if mn > mx:
            mn, mx = mx, mn

        dt_from = filters.parse_date(self.filter_from.text())
        dt_to = filters.parse_date(self.filter_to.text())
        if dt_to:
            dt_to = dt_to.replace(hour=23, minute=59, second=59)

        criteria = filters.RiskFilterCriteria(
            search=(self.filter_search.text() or ""),
            min_score=mn,
            max_score=mx,
            status=(self.filter_status.currentText() or "(any)"),
            category_contains=(self.filter_category.text() or ""),
            owner_contains=(self.filter_owner.text() or ""),
            identified_from=dt_from,
            identified_to=dt_to,
        )
        return filters.filter_risks(risks, criteria)

    def _maybe_expand_title_column(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        hh = self.risks_table.horizontalHeader()

        old = self.risks_table.columnWidth(0)
        self.risks_table.resizeColumnToContents(0)
        contents = self.risks_table.columnWidth(0)

        needed = max(old, contents, hh.sectionSizeHint(0))
        if needed != self.risks_table.columnWidth(0):
            self.risks_table.setColumnWidth(0, needed)

        self._risks_col_widths[pid] = [self.risks_table.columnWidth(c) for c in range(self.risks_table.columnCount())]
        self._fit_table_card()

    def _on_risk_clicked(self, row: int, col: int) -> None:
        t_it = self.risks_table.item(row, 1)
        if not t_it:
            return

        clicked_rid = t_it.data(Qt.UserRole)
        if not clicked_rid:
            return
        clicked_rid = str(clicked_rid)

        if self._editor_dirty and self.current_risk_id and self.current_risk_id != clicked_rid:
            self._commit_editor_changes(refresh=True, select_risk_id=clicked_rid)
            row = self.risks_table.currentRow()
            col = self.risks_table.currentColumn() if self.risks_table.currentColumn() >= 0 else 0

        self.risks_table.setCurrentCell(row, col)

        pid = self.current_project_id
        if not pid:
            return

        r = self._risk_cache.get(clicked_rid)
        if not r:
            return

        self.current_risk_id = r.id
        self.editor_label.setText(f"Editor (editing: {r.title})")
        self.risk_form.set_values(
            title=r.title,
            probability=r.probability,
            impact=r.impact,
            code=r.code,
            description=r.description,
            category=r.category,
            threat=r.threat,
            triggers=r.triggers,
            mitigation_plan=getattr(r, "mitigation_plan", None),
            document_url=getattr(r, "document_url", None),
            owner_user_id=r.owner_user_id,
            status=r.status,
            identified_at=r.identified_at,
            status_changed_at=r.status_changed_at,
            response_at=r.response_at,
            occurred_at=r.occurred_at,
            impact_cost=getattr(r, "impact_cost", None),
            impact_time=getattr(r, "impact_time", None),
            impact_scope=getattr(r, "impact_scope", None),
            impact_quality=getattr(r, "impact_quality", None),
        )
        self._editor_dirty = False
        self._refresh_assessments()

    def _fit_table_card(self, max_height: int = 260) -> None:
        if not hasattr(self, "_table_card"):
            return

        self.risks_table.resizeRowsToContents()

        hh = self.risks_table.horizontalHeader()
        hh.setStyleSheet(
            """
            QHeaderView::section {
                background: white;
                border: none;
                border-bottom: 1px solid #d0d0d0;
                padding: 4px 6px;
            }
            """
        )
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

    def _commit_editor_changes(self, *, refresh: bool, select_risk_id: str | None = None) -> None:
        if not self._editor_dirty:
            return
        if not self.current_risk_id:
            return

        #title = self.risk_form.title.text().strip()
        #if not title:
        #    return

        #p = int(self.risk_form.p.value())
        #i = int(self.risk_form.i.value())

        payload = self.risk_form.get_payload()
        if not payload.get("title"):
            return
        
        #title = payload["title"]
        #p = int(payload["probability"])
        #i = int(payload["impact"])

        try:
            #self.backend.update_risk(self.current_risk_id, title=title, probability=p, impact=i, **payload)
            # payload already contains title/probability/impact
            self.backend.update_risk(self.current_risk_id, **payload)
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))
            return

        self._editor_dirty = False

        if refresh:
            self._refresh_risks(select_risk_id=select_risk_id or self.current_risk_id)
            self._refresh_matrix()
            self._maybe_expand_title_column()

    def _start_new_risk(self) -> None:
        self._commit_editor_changes(refresh=True)

        self.current_risk_id = None
        self.editor_label.setText("Editor (new risk)")
        #self.risk_form.set_values("", 3, 3)
        self.risk_form.set_values(title="", probability=3, impact=3)
        self._editor_dirty = False

        self.risks_table.clearSelection()
        self.risks_table.setCurrentItem(None)

    def _save_risk(self, payload: dict) -> None:
        pid = self.current_project_id
        if not pid:
            QMessageBox.warning(self, "No project", "Select a project first.")
            return

        # Make a local copy and split core fields from metadata to avoid duplicate kwargs
        data = dict(payload or {})
        title = (data.pop("title", "") or "").strip()
        p = int(data.pop("probability", 3) or 3)
        i = int(data.pop("impact", 3) or 3)
        
        # Normalize empty strings to None for optional fields
        for k in [
            "code", "description", "category", "threat", "triggers",
            "mitigation_plan", "document_url", "owner_user_id", "status",
            "identified_at", "status_changed_at", "response_at", "occurred_at",
        ]:
            if k in data and isinstance(data[k], str) and not data[k].strip():
                data[k] = None

        if self.current_risk_id:
            rid = self.current_risk_id
            prev = self._risk_cache.get(rid)
            prev_status = (prev.status or "") if prev else ""
            new_status = (data.get("status") or "")
            if new_status and new_status != prev_status:
                data["status_changed_at"] = datetime.utcnow().isoformat()
            try:
                # UPDATE (do not create a new row)
                self.backend.update_risk(rid, title=title, probability=p, impact=i, **data)
            except Exception as e:
                QMessageBox.critical(self, "Backend error", str(e))
                return

            self._editor_dirty = False
            self._refresh_risks(select_risk_id=rid)
            self.editor_label.setText(f"Editor (editing: {title})")

        else:
            # default identified_at for new item if empty
            if not data.get("identified_at"):
                data["identified_at"] = datetime.utcnow().isoformat()
            try:
                r = self.backend.create_risk(pid, title=title, probability=p, impact=i, **data)
            except Exception as e:
                QMessageBox.critical(self, "Backend error", str(e))
                return

            self._editor_dirty = False
            self._refresh_risks(select_risk_id=r.id)
            self.current_risk_id = None
            self.editor_label.setText("Editor (new risk)")
            self.risk_form.set_values()

        self._refresh_matrix()
