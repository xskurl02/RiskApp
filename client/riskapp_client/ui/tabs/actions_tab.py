"""Actions tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractScrollArea,
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from riskapp_client.ui.components.custom_gui_widgets import CrispHeader, setup_readonly_table


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
        setup_readonly_table(self.actions_table)
        self.actions_table.cellClicked.connect(on_action_clicked)

        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.setCornerButtonEnabled(False)
        # Make the table frame wrap the columns (like Risks/Opportunities).
        self.actions_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.actions_table.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)

        self.actions_table.setShowGrid(False)
        header = CrispHeader(Qt.Horizontal, self.actions_table, line_color="#d0d0d0")
        self.actions_table.setHorizontalHeader(header)

        hh = self.actions_table.horizontalHeader()
        hh.setSectionsClickable(False)
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignCenter)
        # Don't stretch sections to the full viewport; we want the frame to hug the columns.
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.actions_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d0d0d0;
                border-radius: 0px;
                background: white;
                selection-background-color: transparent;
                selection-color: black;
            }
        """)

        title_label = QLabel("Actions (mitigation/contingency/exploit)")
        layout.addWidget(title_label)

        self.table_card = QFrame()
        self.table_card.setObjectName("table_card")
        self.table_card.setStyleSheet(
            "#table_card { border: 1px solid #d0d0d0; border-radius: 8px; background: white; }"
        )
        card_layout = QVBoxLayout(self.table_card)
        card_layout.setContentsMargins(16, 12, 12, 12)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.actions_table, 1)
        self.table_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.editor_card = QFrame()
        self.editor_card.setObjectName("editor_card")
        self.editor_card.setStyleSheet(
            "#editor_card { border: 1px solid #d0d0d0; border-radius: 8px; background: white; }"
        )
        editor_layout = QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(16, 12, 12, 12)

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

        editor_layout.addWidget(self.action_editor_label)
        editor_layout.addLayout(form)
        editor_layout.addLayout(btns)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self.table_card)
        split.addWidget(self.editor_card)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([400, 400])
        split.setStyleSheet(
            "QSplitter::handle:vertical { background: transparent; border: none; }"
        )

        layout.addWidget(split)

        self.setLayout(layout)
