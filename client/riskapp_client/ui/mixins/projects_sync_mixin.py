"""MainWindow mixin for project selection and sync controls.

Loads projects, refreshes all tabs when the project changes, and runs sync.
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QListWidgetItem,
    QMessageBox,
)


class ProjectsSyncMixin:
    """MainWindow mixin: ProjectsSyncMixin"""

    def _refresh_all_views(self, *, select_id: str | None = None) -> None:
        """Refresh all project-scoped tabs from the backend/local store."""
        self._refresh_risks(select_id=select_id)
        for fn in (
            self._refresh_action_risk_combo,
            self._refresh_actions,
            self._maybe_expand_title_column,
            self._refresh_matrix,
            self._refresh_top_history,
            self._refresh_assessments,
            self._refresh_opportunities,
            self._refresh_action_opp_combo,
            self._refresh_members,
            self._update_sync_status,
        ):
            fn()

    def _load_projects(self, *, select_project_id: str | None = None) -> None:
        self.project_list.clear()
        projects = self._call_backend("Backend error", self.backend.list_projects)
        if projects is None:
            return

        for p in projects:
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, p.id)
            self.project_list.addItem(item)

        if self.project_list.count() <= 0:
            return

        if select_project_id:
            for i in range(self.project_list.count()):
                it = self.project_list.item(i)
                if str(it.data(Qt.UserRole)) == str(select_project_id):
                    self.project_list.setCurrentRow(i)
                    return

        self.project_list.setCurrentRow(0)

    def _on_project_selected(self) -> None:
        # Best-effort commit of in-flight edits before switching projects.
        with contextlib.suppress(Exception):
            self._commit_editor_changes(refresh=False)
        with contextlib.suppress(Exception):
            self._commit_opp_editor_changes(refresh=False)

        items = self.project_list.selectedItems()
        if not items:
            return

        if self.current_project_id:
            self._risks_col_widths[self.current_project_id] = [
                self.risks_table.columnWidth(c)
                for c in range(self.risks_table.columnCount())
            ]

        self.current_project_id = items[0].data(Qt.UserRole)
        self.current_risk_id = None
        self.current_opportunity_id = None
        self.current_assessment_item_id = None
        self.current_assessment_item_type = "risk"
        self.editor_label.setText("Editor (new risk)")
        # self.risk_form.set_values("", 3, 3)
        self.risk_form.set_values(title="", probability=3, impact=3)

        self._refresh_all_views()
        self._start_new_action()

    def _update_sync_status(self) -> None:
        pid = self.current_project_id
        pending = 0
        blocked = 0
        can_sync = False

        if hasattr(self.backend, "pending_count"):
            try:
                pending = self.backend.pending_count(pid)  # type: ignore[attr-defined]
            except Exception:
                pending = 0

        if hasattr(self.backend, "blocked_count"):
            try:
                blocked = self.backend.blocked_count(pid)  # type: ignore[attr-defined]
            except Exception:
                blocked = 0

        if hasattr(self.backend, "can_sync"):
            try:
                can_sync = bool(self.backend.can_sync())  # type: ignore[attr-defined]
            except Exception:
                can_sync = False

        self.sync_btn.setEnabled(bool(pid) and can_sync)
        mode = "ONLINE" if can_sync else "OFFLINE"
        extra = f" · blocked: {blocked}" if blocked else ""
        self.sync_status.setText(f"{mode} · pending changes: {pending}{extra}")

    def _sync_now(self) -> None:
        pid = self.current_project_id
        if not pid:
            return
        if not hasattr(self.backend, "sync_project"):
            QMessageBox.information(self, "Sync", "This backend does not support sync.")
            return
        summary = self._call_backend("Sync failed", self.backend.sync_project, pid)  # type: ignore[attr-defined]
        if summary is None:
            self._update_sync_status()
            return

        # If the sync promoted a local-only project to a server project,
        # reload project list and keep the user on the migrated project.
        migrated_to = summary.get("project_id_migrated_to")
        if migrated_to:
            self._load_projects(select_project_id=str(migrated_to))
            self.current_project_id = str(migrated_to)

        # refresh UI from local store after sync
        self._refresh_all_views(select_id=self.current_risk_id)

        QMessageBox.information(
            self,
            "Sync complete",
            f"Pushed: {summary.get('pushed')}\n"
            f"Conflicts rebased: {summary.get('conflicts')}\n"
            f"Errors blocked: {summary.get('errors')}\n"
            f"Pulled risks: {summary.get('pulled_risks')}",
        )
