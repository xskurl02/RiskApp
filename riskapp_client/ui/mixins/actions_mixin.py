"""MainWindow mixin for the Actions tab.

Populates the actions table and drives the actions editor (create/update).
"""

from __future__ import annotations

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

class ActionsMixin:
    """MainWindow mixin: ActionsMixin"""
    def _toggle_action_target_inputs(self) -> None:
        is_risk = (self.action_target_type.currentText() == "risk")
        self.action_risk_combo.setEnabled(is_risk)
        self.action_opp_combo.setEnabled(not is_risk)

    def _refresh_action_risk_combo(self) -> None:
        pid = self.current_project_id
        if not pid:
            return
        risks = self.backend.list_risks(pid)
        self._risk_title_by_id = {r.id: r.title for r in risks}

        self.action_risk_combo.blockSignals(True)
        self.action_risk_combo.clear()
        for r in risks:
            self.action_risk_combo.addItem(r.title, r.id)
        self.action_risk_combo.blockSignals(False)

    def _refresh_action_opp_combo(self) -> None:
        self.action_opp_combo.setCurrentIndex(-1)
        pid = self.current_project_id
        if not pid:
            return
        opps = self.backend.list_opportunities(pid)
        self._opp_title_by_id = {o.id: o.title for o in opps}

        self.action_opp_combo.blockSignals(True)
        self.action_opp_combo.clear()
        for o in opps:
            self.action_opp_combo.addItem(o.title, o.id)
        self.action_opp_combo.blockSignals(False)

    def _refresh_actions(self, select_action_id: str | None = None) -> None:
        pid = self.current_project_id
        if not pid:
            return

        try:
            actions = self.backend.list_actions(pid)
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))
            return

        self.actions_table.setRowCount(0)
        for a in actions:
            row = self.actions_table.rowCount()
            self.actions_table.insertRow(row)

            title_it = QTableWidgetItem(a.title)
            title_it.setData(Qt.UserRole, a.id)
            self.actions_table.setItem(row, 0, title_it)

            self.actions_table.setItem(row, 1, QTableWidgetItem(a.kind))
            self.actions_table.setItem(row, 2, QTableWidgetItem(a.status))

            target = ""
            if a.risk_id:
                target = f"risk: {self._risk_title_by_id.get(a.risk_id, a.risk_id)}"
            elif a.opportunity_id:
                target = f"opp: {self._opp_title_by_id.get(a.opportunity_id, a.opportunity_id)}"
            self.actions_table.setItem(row, 3, QTableWidgetItem(target))

            self.actions_table.setItem(row, 4, QTableWidgetItem(a.owner_user_id or ""))

        if select_action_id:
            for row in range(self.actions_table.rowCount()):
                it = self.actions_table.item(row, 0)
                if it and str(it.data(Qt.UserRole)) == str(select_action_id):
                    self.actions_table.selectRow(row)
                    self.actions_table.setCurrentCell(row, 0)
                    break

    def _on_action_clicked(self, row: int, _col: int) -> None:
        it = self.actions_table.item(row, 0)
        if not it:
            return
        aid = str(it.data(Qt.UserRole))

        pid = self.current_project_id
        if not pid:
            return

        actions = self.backend.list_actions(pid)
        a = next((x for x in actions if x.id == aid), None)
        if not a:
            return

        self.current_action_id = a.id
        self.action_editor_label.setText(f"Editor (editing: {a.title})")

        if a.risk_id:
            self.action_target_type.setCurrentText("risk")
            # set combo by id
            idx = self.action_risk_combo.findData(a.risk_id)
            if idx >= 0:
                self.action_risk_combo.setCurrentIndex(idx)
        else:
            self.action_target_type.setCurrentText("opportunity")
            idx = self.action_opp_combo.findData(a.opportunity_id)
            if idx >= 0:
                self.action_opp_combo.setCurrentIndex(idx)


        self.action_kind.setCurrentText(a.kind)
        self.action_status.setCurrentText(a.status)
        self.action_title.setText(a.title)
        self.action_desc.setPlainText(a.description or "")
        self.action_owner.setText(a.owner_user_id or "")

        self._toggle_action_target_inputs()

    def _start_new_action(self) -> None:
        self.current_action_id = None
        self.action_editor_label.setText("Editor (new action)")
        self.action_target_type.setCurrentText("risk")
        self.action_kind.setCurrentText("mitigation")
        self.action_status.setCurrentText("open")
        self.action_title.setText("")
        self.action_desc.setPlainText("")
        self.action_owner.setText("")
        self.action_opp_combo.setCurrentIndex(-1)
        self._toggle_action_target_inputs()
        self.actions_table.clearSelection()

    def _save_action(self) -> None:
        pid = self.current_project_id
        if not pid:
            QMessageBox.warning(self, "No project", "Select a project first.")
            return

        target_type = self.action_target_type.currentText()
        if target_type == "risk":
            target_id = str(self.action_risk_combo.currentData())
            if not target_id or target_id == "None":
                QMessageBox.warning(self, "Validation", "Pick a risk.")
                return
        else:
            target_id = str(self.action_opp_combo.currentData())
            if not target_id or target_id == "None":
                QMessageBox.warning(self, "Validation", "Pick an opportunity.")
                return


        kind = self.action_kind.currentText()
        status = self.action_status.currentText()
        title = self.action_title.text().strip()
        desc = self.action_desc.toPlainText().strip()
        owner = self.action_owner.text().strip() or None

        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return

        try:
            if self.current_action_id:
                a = self.backend.update_action(
                    self.current_action_id,
                    target_type=target_type,
                    target_id=target_id,
                    kind=kind,
                    title=title,
                    description=desc,
                    status=status,
                    owner_user_id=owner,
                )
            else:
                a = self.backend.create_action(
                    pid,
                    target_type=target_type,
                    target_id=target_id,
                    kind=kind,
                    title=title,
                    description=desc,
                    status=status,
                    owner_user_id=owner,
                )
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))
            return

        self._refresh_actions(select_action_id=a.id)
        self._update_sync_status()
