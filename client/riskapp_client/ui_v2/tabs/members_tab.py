"""Members / roles tab widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QAbstractScrollArea,
    QHeaderView,
    QSizePolicy
)

from riskapp_client.ui_v2.components.custom_gui_widgets import setup_readonly_table
from riskapp_client.ui_v2.tabs.ui_members_tab import Ui_Form as Ui_MembersTab


class MembersTab(QWidget):
    """Project members and role management UI."""

    def __init__(
        self,
        *,
        on_add_or_update_member,
        on_remove_selected_member,
        on_refresh_members,
        on_member_selected,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_MembersTab()
        self.ui.setupUi(self)

        setup_readonly_table(self.ui.members_table, excel_delegate=True)

        # --- EXCEL SIZING & HUGGING THE TABLE ---
        hh = self.ui.members_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        self.ui.members_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.ui.members_table.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        
        # SAFELY push the table to the top left by adding an invisible expanding spring at the bottom
        self.ui.verticalLayout.addStretch()
        # ----------------------------------------

        # --- CONTEXT HELP (HEADER TOOLTIPS) ---
        tooltips = {
            0: "Email: The email address of the team member",
            1: "Role: The permission level (e.g., viewer, member, manager, admin)",
            2: "User ID: The unique internal identifier for this user",
            3: "Added at: When this user was added to the project"
        }
        for col, text in tooltips.items():
            if self.ui.members_table.horizontalHeaderItem(col):
                self.ui.members_table.horizontalHeaderItem(col).setToolTip(text)
        # --------------------------------------

        self.ui.members_table.itemSelectionChanged.connect(on_member_selected)

        self.ui.member_add_btn.clicked.connect(on_add_or_update_member)
        self.ui.member_remove_btn.clicked.connect(on_remove_selected_member)
        self.ui.member_refresh_btn.clicked.connect(on_refresh_members)

        self.members_hint = self.ui.members_hint
        self.member_email = self.ui.member_email
        self.member_role = self.ui.member_role
        self.member_add_btn = self.ui.member_add_btn
        self.member_remove_btn = self.ui.member_remove_btn
        self.member_refresh_btn = self.ui.member_refresh_btn
        self.members_table = self.ui.members_table

        # --- CONTEXT HELP (EDITOR FORM) ---
        self.member_email.setToolTip("Enter the email address of the user to add or update")
        self.member_role.setToolTip("Admins & Managers can edit; Members & Viewers are restricted")
        self.member_add_btn.setToolTip("Add the user to the project, or update their role if they already exist")
        self.member_remove_btn.setToolTip("Remove the selected user from the project")
        self.member_refresh_btn.setToolTip("Reload the members list from the server")
        # ----------------------------------
