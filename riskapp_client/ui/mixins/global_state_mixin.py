"""MainWindow mixin for shared state and cross-cutting UI behavior.

Holds non-UI state, applies permission gating, and implements global event filtering.
"""
from __future__ import annotations

from datetime import datetime
from collections import Counter

from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from riskapp_client.domain.domain_models import Opportunity, Risk

from PySide6.QtCore import QEvent, QObject, Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QApplication, QDateTimeEdit, QLabel, QMessageBox, QTableWidget, QTableWidgetItem  # pylint: disable=no-name-in-module

from riskapp_client.services import permissions
from riskapp_client.domain.scored_entity_fields import DEFAULT_STATUS, ALL_STATUSES

T = TypeVar('T')

class CoreMixin:
    """MainWindow mixin: CoreMixin"""

    def _init_state(self) -> None:
        """Initialize MainWindow state (non-UI fields)."""
        self.current_project_id: str | None = None
        self.current_risk_id: str | None = None
        self.current_opportunity_id: str | None = None
        # Role / permissions (per project)
        self._role_by_project: dict[str, str] = {}
        self.current_role: str = "unknown"
        self._role_assumed: bool = False
        self._offline_mode: bool = False
        # auto-snapshot throttle
        self._last_auto_snapshot_by_project: dict[str, datetime] = {}
        self._opp_title_by_id: dict[str, str] = {}
        self._opp_cache: dict[str, Opportunity] = {}
        self._risk_cache: dict[str, "Risk"] = {}
        self._opp_editor_dirty: bool = False
        self._editor_dirty: bool = False
        self._risks_col_widths: dict[str, list[int]] = {}
        self._risks_last_pid: str | None = None
        self.current_action_id: str | None = None
        self._risk_title_by_id: dict[str, str] = {}

    def _detect_offline_mode(self) -> bool:
        """Return True if this is the OfflineBackend running without a remote (server) connection."""
        return bool(hasattr(self.backend, "remote") and getattr(self.backend, "remote") is None)

    def _set_role_status(self, *, role: str, offline: bool, assumed: bool) -> None:
        self.current_role = (role or "unknown")
        self._offline_mode = bool(offline)
        self._role_assumed = bool(assumed)
        suffix = ""
        if offline:
            suffix += " (offline)"
        if assumed:
            suffix += " (assumed)"
        self.role_status.setText(f"Role: {self.current_role}{suffix}")

    def _apply_permissions(self) -> None:
        """Enable/disable UI controls based on the user's role and online/offline state."""
        pid = self.current_project_id

        # If role is unknown offline, assume member *for local editing only*.
        # This preserves offline-first workflows; server enforcement still applies at sync.
        role_for_local = self.current_role
        assumed_member_offline = False
        if self._offline_mode and role_for_local == "unknown":
            role_for_local = "member"
            assumed_member_offline = True


        can_edit_local = bool(pid) and permissions.role_at_least(role_for_local, "member")
        can_take_snapshots = bool(pid) and (not self._offline_mode) and permissions.role_at_least(self.current_role, "manager")
        can_manage_members = bool(pid) and (not self._offline_mode) and permissions.role_at_least(self.current_role, "admin")

        # Update role label if we auto-assumed member offline.
        if assumed_member_offline and not self._role_assumed:
            suffix = ""
            if self._offline_mode:
                suffix += " (offline)"
            suffix += " (assumed)"
            self.role_status.setText(f"Role: {role_for_local}{suffix}")
            self._role_assumed = True

        # --- Risks / Opportunities editors ---
        for btn, form in [(self.new_risk_btn, self.risk_form), (self.new_opp_btn, self.opp_form)]:
            btn.setEnabled(can_edit_local)
            if hasattr(form, "set_editable"):
                form.set_editable(can_edit_local)
            elif hasattr(form, "btn"):
                form.btn.setEnabled(can_edit_local)

        # --- Actions editor ---
        for w in (
            self.actions_tab.action_target_type,
            self.actions_tab.action_risk_combo,
            self.actions_tab.action_opp_combo,
            self.actions_tab.action_kind,
            self.actions_tab.action_status,
            self.actions_tab.action_title,
            self.actions_tab.action_desc,
            self.actions_tab.action_owner,
            self.actions_tab.action_save_btn,
            self.actions_tab.action_new_btn,
        ):
            w.setEnabled(can_edit_local)

        # --- Assessments ---
        for w in (self.assessments_tab.assess_p, self.assessments_tab.assess_i, self.assessments_tab.assess_notes, self.assessments_tab.assess_save_btn):
            w.setEnabled(can_edit_local)

        # --- Snapshots / history ---
        self.top_tab.snapshot_btn.setEnabled(can_take_snapshots)
        self.top_tab.auto_snapshot_chk.setEnabled(can_take_snapshots)
        self.top_tab.auto_snapshot_kind.setEnabled(can_take_snapshots)
        self.top_tab.auto_snapshot_days.setEnabled(can_take_snapshots)

        # --- Members management (admin only, online only) ---
        self.members_tab.member_email.setEnabled(can_manage_members)
        self.members_tab.member_role.setEnabled(can_manage_members)
        self.members_tab.member_add_btn.setEnabled(can_manage_members)
        self.members_tab.member_remove_btn.setEnabled(can_manage_members)
        
        # Refresh should be allowed when online (any role), and in offline mode it is harmless.
        self.members_tab.member_refresh_btn.setEnabled(bool(pid) and (not self._offline_mode))

    # -------------------------
    # Shared UI helpers (scored entities)
    # -------------------------
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

    def _select_row_by_entity_id(
        self,
        entity_id: str | None,
        *,
        table: QTableWidget,
        id_col: int = 0,
    ) -> None:
        """Select a row in `table` by entity id stored in Qt.UserRole in `id_col`."""
        if not entity_id:
            return
        target = str(entity_id)

        for row in range(table.rowCount()):
            it = table.item(row, id_col)
            if it and str(it.data(Qt.UserRole)) == target:
                table.selectRow(row)
                table.setCurrentCell(row, id_col)
                return

    def _call_backend(self, title: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
        """Call a backend function and show a modal error if it fails."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            QMessageBox.critical(self, title, str(exc))
            return None

    def _update_scored_filter_report(self, label: QLabel, full_count: int, filtered: list[object]) -> None:
        """Render a common filter report for Risk/Opportunity tabs."""
        if not filtered:
            label.setText(f"Showing 0/{full_count}")
            return

        scores = [int(getattr(x, "score", 0) or 0) for x in filtered]
        avg = sum(scores) / len(scores)

        status_counts = Counter((getattr(x, "status", None) or DEFAULT_STATUS) for x in filtered)
        order = list(ALL_STATUSES)
        status_bits = [f"{st} {status_counts[st]}" for st in order if status_counts.get(st)]
        for st, n in status_counts.most_common():
            if st not in order:
                status_bits.append(f"{st} {n}")

        cat_counts = Counter((getattr(x, "category", None) or "(none)") for x in filtered)
        top_cats = [f"{c} {n}" for c, n in cat_counts.most_common(3) if c and c != "(none)"]

        lines = [
            f"Showing {len(filtered)}/{full_count} · score min {min(scores)} · max {max(scores)} · avg {avg:.1f}",
            f"Status: {', '.join(status_bits) if status_bits else '(none)'}",
        ]
        if top_cats:
            lines.append(f"Top categories: {', '.join(top_cats)}")

        label.setText("<br>".join(lines))

    def _clear_table_selection(self, table: QTableWidget) -> None:
        table.clearSelection()
        table.setCurrentItem(None)

    @staticmethod
    def _is_inside(container: object | None, w: object | None) -> bool:
        if not container or not w:
            return False
        try:
            return bool(w is container or container.isAncestorOf(w))  # type: ignore[attr-defined]
        except Exception:
            return False

    def _active_scored_tab_context(self):
        """Return context for the currently active scored-entity tab.

        Returns:
            (tab_widget, table_widget, editor_card, commit_fn, clear_selection_fn)
            or None if the active tab is not a scored-entity tab.
        """
        if not hasattr(self, "tabs"):
            return None
        current = self.tabs.currentWidget()

        if current is getattr(self, "risks_tab", None):
            return (
                current,
                self.risks_table,
                getattr(self, "_editor_card", None),
                lambda: self._commit_editor_changes(refresh=True),
                lambda: self._clear_table_selection(self.risks_table),
            )

        if current is getattr(self, "opps_tab", None):
            editor = getattr(self, "_opp_editor_card", None)
            if editor is None and hasattr(self, "opps_tab"):
                editor = getattr(self.opps_tab, "editor_card", None)
            return (
                current,
                self.opps_table,
                editor,
                lambda: self._commit_opp_editor_changes(refresh=True),
                lambda: self._clear_table_selection(self.opps_table),
            )

        return None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.MouseButtonPress:
            ctx = self._active_scored_tab_context()
            if ctx:
                tab_w, table_w, editor_w, commit_fn, clear_fn = ctx

                try:
                    gp = event.globalPosition().toPoint()
                except Exception:
                    gp = event.globalPos()

                w = QApplication.widgetAt(gp)

                inside_table = self._is_inside(table_w, w)
                inside_editor = self._is_inside(editor_w, w)
                inside_tab = self._is_inside(tab_w, w)

                if (not inside_table) and (not inside_editor):
                    commit_fn()
                    # Only clear the selection if the click happened outside the active tab.
                    # Clicking filters or other in-tab controls should not de-select the current row.
                    if not inside_tab:
                        clear_fn()
        return super().eventFilter(obj, event)

    def _dtedit_to_iso_utc_naive(self, w: QDateTimeEdit) -> str:
        """
        Convert QDateTimeEdit value to ISO string WITHOUT timezone (naive UTC),
        so FastAPI parses it as naive datetime and DB comparisons stay consistent.
        """
        secs = int(w.dateTime().toSecsSinceEpoch())
        return datetime.utcfromtimestamp(secs).replace(microsecond=0).isoformat()
