"""Actions tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ActionsTab(QWidget):
    """Actions list + editor tab."""

    def __init__(
        self,
        *,
        on_action_clicked: Callable[[int, int], None],
        on_save_action: Callable[[], None],
        on_new_action: Callable[[], None],
        on_target_type_changed: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()

        self.actions_table = QTableWidget(0, 5)
        self.actions_table.setHorizontalHeaderLabels(
            ["Title", "Kind", "Status", "Target", "Owner"]
        )
        self.actions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.actions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.actions_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.actions_table.cellClicked.connect(on_action_clicked)

        layout.addWidget(QLabel("Actions (mitigation/contingency/exploit)"))
        layout.addWidget(self.actions_table)

        self.action_editor_label = QLabel("Editor (new action)")

        self.action_target_type = QComboBox()
        self.action_target_type.addItems(["risk", "opportunity"])
        self.action_target_type.currentTextChanged.connect(on_target_type_changed)

        self.action_risk_combo = QComboBox()
        self.action_opp_combo = QComboBox()

        self.action_kind = QComboBox()
        self.action_kind.addItems(["mitigation", "contingency", "exploit"])

        self.action_status = QComboBox()
        self.action_status.addItems(["open", "doing", "done"])

        self.action_title = QLineEdit()
        self.action_desc = QTextEdit()
        self.action_owner = QLineEdit()

        self.action_save_btn = QPushButton("Save")
        self.action_new_btn = QPushButton("New action")
        self.action_save_btn.clicked.connect(on_save_action)
        self.action_new_btn.clicked.connect(on_new_action)

        form = QFormLayout()
        form.addRow("Target type", self.action_target_type)
        form.addRow("Risk", self.action_risk_combo)
        form.addRow("Opportunity", self.action_opp_combo)
        form.addRow("Kind", self.action_kind)
        form.addRow("Status", self.action_status)
        form.addRow("Title", self.action_title)
        form.addRow("Description", self.action_desc)
        form.addRow("Owner user_id (optional)", self.action_owner)

        btns = QHBoxLayout()
        btns.addWidget(self.action_save_btn)
        btns.addWidget(self.action_new_btn)
        btns.addStretch(1)

        layout.addWidget(self.action_editor_label)
        layout.addLayout(form)
        layout.addLayout(btns)

        self.setLayout(layout)
