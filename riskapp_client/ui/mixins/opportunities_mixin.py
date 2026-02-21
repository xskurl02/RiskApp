"""MainWindow mixin for the Opportunities tab.

Filtering, table rendering, editor behavior, and CSV export for opportunities.
"""
from __future__ import annotations
from collections import Counter

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

from riskapp_client.domain.models import Opportunity
from riskapp_client.services import export_csv, filters

class OpportunitiesMixin:
    """MainWindow mixin: OpportunitiesMixin"""

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

    def _select_opp_row_by_id(self, opp_id: str | None) -> None:
        """Select the row in opps_table whose column-0 Qt.UserRole matches opp_id."""
        if not opp_id:
            return
        target = str(opp_id)

        for row in range(self.opps_table.rowCount()):
            it = self.opps_table.item(row, 0)
            if it and str(it.data(Qt.UserRole)) == target:
                self.opps_table.selectRow(row)
                self.opps_table.setCurrentCell(row, 0)
                return

    def _update_opp_filter_report(self, full: list[Opportunity], filtered: list[Opportunity]) -> None:
        """Render the opportunities filter report label based on the displayed subset."""
        if not filtered:
            self.opp_filter_report.setText(f"Showing 0/{len(full)}")
            return

        scores = [o.score for o in filtered]
        avg = sum(scores) / len(scores)

        status_counts = Counter((o.status or "concept") for o in filtered)
        order = ["active", "concept", "closed", "happened", "deleted"]
        status_bits = [f"{st} {status_counts[st]}" for st in order if status_counts.get(st)]
        for st, n in status_counts.most_common():
            if st not in order:
                status_bits.append(f"{st} {n}")

        cat_counts = Counter((o.category or "(none)") for o in filtered)
        top_cats = [f"{c} {n}" for c, n in cat_counts.most_common(3) if c and c != "(none)"]

        lines = [
            f"Showing {len(filtered)}/{len(full)} · score min {min(scores)} · max {max(scores)} · avg {avg:.1f}",
            f"Status: {', '.join(status_bits) if status_bits else '(none)'}",
        ]
        if top_cats:
            lines.append(f"Top categories: {', '.join(top_cats)}")

        self.opp_filter_report.setText("<br>".join(lines))
    def _export_opportunities_csv(self) -> None:
        if not self.current_project_id:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export opportunities CSV", "opportunities.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        rows = list(self._opp_cache.values())
        rows.sort(key=lambda o: (o.score, o.title), reverse=True)
        export_csv.export_opportunities(path, rows)

    def _refresh_opportunities(self, select_id: str | None = None) -> None:
        pid = self.current_project_id
        if not pid:
            return

        try:
            full = self.backend.list_opportunities(pid)
        except Exception as exc:
            QMessageBox.critical(self, "Backend error", str(exc))
            return

        filtered = self._apply_opportunity_filters(full)

        self._update_opp_filter_report(full, filtered)

        # Editor selection uses only the displayed subset.
        self._opp_cache = {o.id: o for o in filtered}
        # Actions tab uses a full mapping (not filtered) for target selection.
        self._opp_title_by_id = {o.id: o.title for o in full}

        # Populate table
        self.opps_table.setRowCount(len(filtered))
        for row, o in enumerate(filtered):
            self.opps_table.setItem(row, 0, self._mk_item(o.code or "", entity_id=o.id))
            self.opps_table.setItem(row, 1, self._mk_item(o.title, entity_id=o.id))
            self.opps_table.setItem(row, 2, self._mk_item(o.category or ""))
            self.opps_table.setItem(row, 3, self._mk_item(o.status or ""))
            self.opps_table.setItem(row, 4, self._mk_item(o.owner_user_id or ""))
            self.opps_table.setItem(row, 5, self._mk_item(str(o.probability), align_center=True))
            self.opps_table.setItem(row, 6, self._mk_item(str(o.impact), align_center=True))
            self.opps_table.setItem(row, 7, self._mk_item(str(o.score), align_center=True))

        self._select_opp_row_by_id(select_id)
        self.opps_table.resizeColumnsToContents()

    def _apply_opportunity_filters(self, opps: list[Opportunity]) -> list[Opportunity]:
        mn = int(self.opp_filter_min_score.value())
        mx = int(self.opp_filter_max_score.value())
        if mn > mx:
            mn, mx = mx, mn

        dt_from = filters.parse_date(self.opp_filter_from.text())
        dt_to = filters.parse_date(self.opp_filter_to.text())
        if dt_to:
            dt_to = dt_to.replace(hour=23, minute=59, second=59)
        criteria = filters.OpportunityFilterCriteria(
            search=(self.opp_filter_search.text() or ""),
            min_score=mn,
            max_score=mx,
            status=(self.opp_filter_status.currentText() or "(any)"),
            category_contains=(self.opp_filter_category.text() or ""),
            owner_contains=(self.opp_filter_owner.text() or ""),
            identified_from=dt_from,
            identified_to=dt_to,
        )
        return filters.filter_opportunities(opps, criteria)

    def _on_opportunity_clicked(self, row: int, _col: int) -> None:
        it = self.opps_table.item(row, 0)
        if not it:
            return
        oid = str(it.data(Qt.UserRole) or "")
        if not oid:
            return

        # optional auto-commit before switching
        if self._opp_editor_dirty and self.current_opportunity_id and self.current_opportunity_id != oid:
            #title = self.opp_form.title.text().strip()
            #if title:
            #    self.backend.update_opportunity(self.current_opportunity_id, title, int(self.opp_form.p.value()), int(self.opp_form.i.value()))
            payload = self.opp_form.get_payload()
            if payload.get("title"):
                payload["probability"] = int(payload["probability"])
                payload["impact"] = int(payload["impact"])
                self.backend.update_opportunity(self.current_opportunity_id, **payload)
            self._opp_editor_dirty = False
            self._refresh_opportunities(select_id=oid)

        o = self._opp_cache.get(oid)
        if not o:
            return

        self.current_opportunity_id = o.id
        self.opp_editor_label.setText(f"Editor (editing: {o.title})")
        self.opp_form.set_values(
            title=o.title,
            probability=o.probability,
            impact=o.impact,
            code=o.code,
            description=o.description,
            category=o.category,
            threat=o.threat,
            triggers=o.triggers,
            mitigation_plan=getattr(o, "mitigation_plan", None),
            document_url=getattr(o, "document_url", None),
            owner_user_id=o.owner_user_id,
            status=o.status,
            identified_at=o.identified_at,
            status_changed_at=o.status_changed_at,
            response_at=o.response_at,
            occurred_at=o.occurred_at,
            impact_cost=getattr(o, "impact_cost", None),
            impact_time=getattr(o, "impact_time", None),
            impact_scope=getattr(o, "impact_scope", None),
            impact_quality=getattr(o, "impact_quality", None),
        )
        self._opp_editor_dirty = False

    def _start_new_opportunity(self) -> None:
        self.current_opportunity_id = None
        self.opp_editor_label.setText("Editor (new opportunity)")
        #self.opp_form.set_values("", 3, 3)
        self.opp_form.set_values(title="", probability=3, impact=3)
        self._opp_editor_dirty = False
        self.opps_table.clearSelection()

    def _save_opportunity(self, payload: dict) -> None:
        pid = self.current_project_id
        if not pid:
            QMessageBox.warning(self, "No project", "Select a project first.")
            return
        try:
            #title = payload["title"]
            #p = int(payload["probability"])
            #i = int(payload["impact"])
            payload["probability"] = int(payload["probability"])
            payload["impact"] = int(payload["impact"])
            if self.current_opportunity_id:
                oid = self.current_opportunity_id
                #self.backend.update_opportunity(oid, title=title, probability=p, impact=i, **payload)
                self.backend.update_opportunity(oid, **payload)
                self._refresh_opportunities(select_id=oid)
                #self.opp_editor_label.setText(f"Editor (editing: {title})")
                self.opp_editor_label.setText(f"Editor (editing: {payload.get('title','')})")
            else:
                #o = self.backend.create_opportunity(pid, title=title, probability=p, impact=i, **payload)
                o = self.backend.create_opportunity(pid, **payload)
                self._refresh_opportunities(select_id=o.id)
                self._start_new_opportunity()
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))
            return

        self._opp_editor_dirty = False
        # keep Actions target list in sync
        self._refresh_action_opp_combo()
        self._refresh_actions()

    # --- Members / roles UI ---
