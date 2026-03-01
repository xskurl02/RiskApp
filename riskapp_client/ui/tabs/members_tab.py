"""Members / roles tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from riskapp_client.ui.components.custom_gui_widgets import setup_readonly_table


class MembersTab(QWidget):
    """Project members and role management UI."""

    def __init__(
        self,
        *,
        on_add_or_update_member: Callable[[], None],
        on_remove_selected_member: Callable[[], None],
        on_refresh_members: Callable[[], None],
        on_member_selected: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()

        self.members_hint = QLabel("Project members and roles (admin only for changes).")
        layout.addWidget(self.members_hint)

        controls = QHBoxLayout()

        self.member_email = QLineEdit()
        self.member_email.setPlaceholderText("user@example.com")

        self.member_role = QComboBox()
        self.member_role.setEditable(True)
        self.member_role.addItems(["viewer", "member", "manager", "admin"])

        self.member_add_btn = QPushButton("Add/Update")
        self.member_add_btn.clicked.connect(on_add_or_update_member)

        self.member_remove_btn = QPushButton("Remove selected")
        self.member_remove_btn.clicked.connect(on_remove_selected_member)

        self.member_refresh_btn = QPushButton("Refresh")
        self.member_refresh_btn.clicked.connect(on_refresh_members)

        controls.addWidget(QLabel("Email"))
        controls.addWidget(self.member_email, 2)
        controls.addWidget(QLabel("Role"))
        controls.addWidget(self.member_role, 1)
        controls.addWidget(self.member_add_btn)
        controls.addWidget(self.member_remove_btn)
        controls.addWidget(self.member_refresh_btn)

        layout.addLayout(controls)

        self.members_table = QTableWidget(0, 4)
        self.members_table.setHorizontalHeaderLabels(["Email", "Role", "User ID", "Added at"])

        setup_readonly_table(self.members_table, excel_delegate=True)
        self.members_table.itemSelectionChanged.connect(on_member_selected)

        layout.addWidget(self.members_table)
        self.setLayout(layout)
