"""MainWindow mixin for shared state and cross-cutting UI behavior.

Holds non-UI state, applies permission gating, and implements global event filtering.
"""
from __future__ import annotations

from datetime import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from riskapp_client.domain.models import Opportunity, Risk

from PySide6.QtCore import QEvent, QObject  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QApplication, QDateTimeEdit  # pylint: disable=no-name-in-module

from riskapp_client.services import permissions

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
        self.new_risk_btn.setEnabled(can_edit_local)
        if hasattr(self.risk_form, "set_editable"):
            self.risk_form.set_editable(can_edit_local)  # type: ignore[attr-defined]
        else:
            # fallback: at least disable Save
            if hasattr(self.risk_form, "btn"):
                self.risk_form.btn.setEnabled(can_edit_local)  # type: ignore[attr-defined]

        self.new_opp_btn.setEnabled(can_edit_local)
        if hasattr(self.opp_form, "set_editable"):
            self.opp_form.set_editable(can_edit_local)  # type: ignore[attr-defined]
        else:
            if hasattr(self.opp_form, "btn"):
                self.opp_form.btn.setEnabled(can_edit_local)  # type: ignore[attr-defined]

        # --- Actions editor ---
        for w in (
            self.action_target_type,
            self.action_risk_combo,
            self.action_opp_combo,
            self.action_kind,
            self.action_status,
            self.action_title,
            self.action_desc,
            self.action_owner,
            self.action_save_btn,
            self.action_new_btn,
        ):
            w.setEnabled(can_edit_local)

        # --- Assessments ---
        for w in (self.assess_p, self.assess_i, self.assess_notes, self.assess_save_btn):
            w.setEnabled(can_edit_local)

        # --- Snapshots / history ---
        self.snapshot_btn.setEnabled(can_take_snapshots)
        self.auto_snapshot_chk.setEnabled(can_take_snapshots)
        self.auto_snapshot_kind.setEnabled(can_take_snapshots)
        self.auto_snapshot_days.setEnabled(can_take_snapshots)

        # --- Members management (admin only, online only) ---
        self.member_email.setEnabled(can_manage_members)
        self.member_role.setEnabled(can_manage_members)
        self.member_add_btn.setEnabled(can_manage_members)
        self.member_remove_btn.setEnabled(can_manage_members)
        # Refresh should be allowed when online (any role), and in offline mode it is harmless.
        self.member_refresh_btn.setEnabled(bool(pid) and (not self._offline_mode))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.MouseButtonPress:
            try:
                gp = event.globalPosition().toPoint()
            except Exception:
                gp = event.globalPos()

            w = QApplication.widgetAt(gp)
            clicked_inside_risks_table = bool(w) and (w is self.risks_table or self.risks_table.isAncestorOf(w))
            clicked_inside_editor = bool(w) and (w is self._editor_card or self._editor_card.isAncestorOf(w))

            if (not clicked_inside_risks_table) and (not clicked_inside_editor):
                self._commit_editor_changes(refresh=True)
                self.risks_table.clearSelection()
                self.risks_table.setCurrentItem(None)

        return super().eventFilter(obj, event)

    def _dtedit_to_iso_utc_naive(self, w: QDateTimeEdit) -> str:
        """
        Convert QDateTimeEdit value to ISO string WITHOUT timezone (naive UTC),
        so FastAPI parses it as naive datetime and DB comparisons stay consistent.
        """
        secs = int(w.dateTime().toSecsSinceEpoch())
        return datetime.utcfromtimestamp(secs).replace(microsecond=0).isoformat()
