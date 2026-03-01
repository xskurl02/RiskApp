from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox
from riskapp_client.ui.mixins.scored_entities_ui_helpers import (
    date_bounds, form_values_for_entity, populate_scored_table, score_bounds
)
from riskapp_client.utils.text_normalization_helpers import norm_optional_text_fields

class ScoredEntityMixin:
    """Jednotný mixin pro Rizika a Příležitosti. Odbourává duplicitní kód."""

    def _export_entity_csv(self, filename: str, cache: dict, export_fn) -> None:
        if not self.current_project_id:
            return
        path, _ = QFileDialog.getSaveFileName(self, f"Export {filename}", filename, "CSV Files (*.csv)")
        if path:
            rows = list(cache.values())
            rows.sort(key=lambda x: (x.score, x.title), reverse=True)
            export_fn(path, rows)

    def _refresh_entity(self, pid: str, list_backend_fn, filter_fn, criteria_cls, report_widget, table_widget, filters_dict, mk_item_fn, select_id: str | None = None) -> dict | None:
        full = self._call_backend("Backend error", list_backend_fn, pid)
        if full is None: return None
        
        mn, mx = score_bounds(filters_dict["min_score"], filters_dict["max_score"])
        dt_from, dt_to = date_bounds(filters_dict["from_date"], filters_dict["to_date"])
        
        criteria = criteria_cls(
            search=(filters_dict["search"].text() or ""),
            min_score=mn, max_score=mx,
            status=(filters_dict["status"].currentText() or "(any)"),
            category_contains=(filters_dict["category"].text() or ""),
            owner_contains=(filters_dict["owner"].text() or ""),
            identified_from=dt_from, identified_to=dt_to,
        )
        filtered = filter_fn(full, criteria)
        self._update_scored_filter_report(report_widget, len(full), list(filtered))
        cache = populate_scored_table(table_widget, list(filtered), mk_item=mk_item_fn)
        self._select_row_by_entity_id(select_id, table=table_widget)
        return cache

    def _on_entity_clicked(self, row: int, col: int, table, cache, current_id, editor_dirty, commit_fn, form, label_widget, label_prefix) -> str | None:
        t_it = table.item(row, 1)
        if not t_it: return None
        clicked_id = str(t_it.data(Qt.UserRole))
        if not clicked_id: return None

        if editor_dirty and current_id and current_id != clicked_id:
            commit_fn(refresh=True, select_id=clicked_id)
            row = table.currentRow()
            col = max(0, table.currentColumn())

        table.setCurrentCell(row, col)
        if not self.current_project_id: return None

        ent = cache.get(clicked_id)
        if not ent: return None

        form.set_values(**form_values_for_entity(ent))
        label_widget.setText(f"{label_prefix} (editing: {ent.title})")
        return ent.id

    def _commit_entity_editor_changes(self, current_id, editor_dirty, form, update_backend_fn, refresh_fn, select_id) -> bool:
        if not editor_dirty or not current_id: return False
        payload = form.get_payload()
        if not payload.get("title"): return False
        if self._call_backend("Backend error", update_backend_fn, current_id, **payload) is None: return False
        if refresh_fn: refresh_fn(select_id=select_id or current_id)
        return True

    def _save_entity(self, payload, current_id, update_backend_fn, create_backend_fn, refresh_fn, form, label_widget, label_prefix, extra_refreshes) -> bool:
        pid = self.current_project_id
        if not pid:
            QMessageBox.warning(self, "No project", "Select a project first.")
            return False

        data = dict(payload or {})
        title = (data.pop("title", "") or "").strip()
        p = int(data.pop("probability", 3) or 3)
        i = int(data.pop("impact", 3) or 3)

        norm_optional_text_fields(data, [
            "code", "description", "category", "threat", "triggers", "mitigation_plan", 
            "document_url", "owner_user_id", "status", "identified_at", "status_changed_at", "response_at", "occurred_at"
        ])

        if current_id:
            if self._call_backend("Backend error", update_backend_fn, current_id, title=title, probability=p, impact=i, **data) is None: return False
            label_widget.setText(f"{label_prefix} (editing: {title})")
        else:
            ent = self._call_backend("Backend error", create_backend_fn, pid, title=title, probability=p, impact=i, **data)
            if ent is None: return False
            current_id = ent.id
            form.set_values()
            label_widget.setText(f"{label_prefix} (new)")

        if refresh_fn: refresh_fn(select_id=current_id)
        for ref in extra_refreshes: ref()
        return True