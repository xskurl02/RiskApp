"""MainWindow mixin for project members/roles management.

Fetches members (online only), updates role state, and controls admin operations.
"""

from __future__ import annotations

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

from riskapp_client.domain.models import Member

class MembersMixin:
    """MainWindow mixin: MembersMixin"""
    def _refresh_members(self) -> None:
        pid = self.current_project_id
        self.members_table.setRowCount(0)

        offline = self._detect_offline_mode()
        if not pid:
            self.members_hint.setText("Select a project to view members/roles.")
            self._set_role_status(role="unknown", offline=offline, assumed=False)
            self._apply_permissions()
            return

        members: list[Member] = []

        if offline:
            self.members_hint.setText("Offline mode: members/roles can be managed only when connected to the server.")
        else:
            self.members_hint.setText("Project members and roles (admin only for changes).")
            try:
                members = self.backend.list_members(pid)  # type: ignore[attr-defined]
            except Exception as e:
                QMessageBox.warning(self, "Members", str(e))
                members = []

        # Fill members table (if available)
        self.members_table.setRowCount(len(members))
        for row, m in enumerate(members):
            email_item = QTableWidgetItem(m.email)
            email_item.setData(Qt.UserRole, m.user_id)  # keep user_id for remove
            self.members_table.setItem(row, 0, email_item)
            self.members_table.setItem(row, 1, QTableWidgetItem(m.role))
            self.members_table.setItem(row, 2, QTableWidgetItem(m.user_id))
            self.members_table.setItem(row, 3, QTableWidgetItem(m.created_at or ""))

        # Populate Owner dropdowns in the Risk/Opportunity editors
        try:
            if hasattr(self.risk_form, "set_members"):
                self.risk_form.set_members(members)
            if hasattr(self.opp_form, "set_members"):
                self.opp_form.set_members(members)
        except Exception:
            pass

        self.members_table.resizeColumnsToContents()
        self.members_table.horizontalHeader().setStretchLastSection(True)

        # Determine current user's role for this project.
        role = "unknown"
        try:
            uid = self.backend.current_user_id()
        except Exception:
            uid = None

        if members and uid:
            for m in members:
                if str(m.user_id) == str(uid):
                    role = (m.role or "viewer")
                    break
            if role != "unknown":
                self._role_by_project[pid] = role
        else:
            # Offline or failed to fetch members: fall back to cached role (if any)
            role = self._role_by_project.get(pid, "unknown")

        self._set_role_status(role=role, offline=offline, assumed=False)
        self._apply_permissions()

    def _on_member_selected(self) -> None:
        items = self.members_table.selectedItems()
        if not items:
            return
        # First column holds email and user_id (Qt.UserRole)
        email = self.members_table.item(items[0].row(), 0).text()
        role = self.members_table.item(items[0].row(), 1).text()
        self.member_email.setText(email)
        idx = self.member_role.findText(role)
        if idx >= 0:
            self.member_role.setCurrentIndex(idx)
        else:
            self.member_role.setEditText(role)

    def _add_or_update_member(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        email = (self.member_email.text() or "").strip()
        role = (self.member_role.currentText() or "").strip() or "viewer"

        if not email or "@" not in email:
            QMessageBox.warning(self, "Validation", "Please enter a valid email.")
            return

        try:
            self.backend.add_member(pid, user_email=email, role=role)  # type: ignore[attr-defined]
        except Exception as e:
            QMessageBox.warning(self, "Members", str(e))
            return

        self.member_email.setText("")
        self._refresh_members()

    def _remove_selected_member(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        items = self.members_table.selectedItems()
        if not items:
            QMessageBox.information(self, "Members", "Select a member first.")
            return

        row = items[0].row()
        email_item = self.members_table.item(row, 0)
        user_id = email_item.data(Qt.UserRole)
        email = email_item.text()

        if not user_id:
            QMessageBox.warning(self, "Members", "Missing member user_id.")
            return

        if QMessageBox.question(
            self,
            "Remove member",
            f"Remove {email} from this project?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        try:
            self.backend.remove_member(pid, member_user_id=str(user_id))  # type: ignore[attr-defined]
        except Exception as e:
            QMessageBox.warning(self, "Members", str(e))
            return

        self._refresh_members()
