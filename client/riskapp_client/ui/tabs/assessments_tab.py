"""Assessments tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractScrollArea,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from riskapp_client.ui.components.custom_gui_widgets import CrispHeader, setup_readonly_table


class AssessmentsTab(QWidget):
    """Assessments view + 'my assessment' editor."""

    def __init__(
        self,
        *,
        on_save_assessment: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Assessments (per-user P/I + notes)"))

        row = QHBoxLayout()

        self.assess_p = QSpinBox()
        self.assess_p.setRange(1, 5)
        self.assess_p.setValue(3)

        self.assess_i = QSpinBox()
        self.assess_i.setRange(1, 5)
        self.assess_i.setValue(3)

        self.assess_notes = QLineEdit()
        self.assess_notes.setPlaceholderText("Notes…")

        self.assess_save_btn = QPushButton("Save my assessment")
        self.assess_save_btn.clicked.connect(on_save_assessment)

        row.addWidget(QLabel("P"))
        row.addWidget(self.assess_p)
        row.addWidget(QLabel("I"))
        row.addWidget(self.assess_i)
        row.addWidget(QLabel("Notes"))
        row.addWidget(self.assess_notes, 2)
        row.addWidget(self.assess_save_btn)
        row.addStretch(1)

        self.assessments_table = QTableWidget(0, 6)
        self.assessments_table.setHorizontalHeaderLabels(
            ["Assessor", "P", "I", "Score", "Notes", "Updated"]
        )
        setup_readonly_table(self.assessments_table)

        self.assessments_table.verticalHeader().setVisible(False)
        self.assessments_table.setCornerButtonEnabled(False)
        # Make the table frame wrap the columns (like Risks/Opportunities).
        self.assessments_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.assessments_table.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)

        self.assessments_table.setShowGrid(False)
        header = CrispHeader(Qt.Horizontal, self.assessments_table, line_color="#d0d0d0")
        self.assessments_table.setHorizontalHeader(header)

        hh = self.assessments_table.horizontalHeader()
        hh.setSectionsClickable(False)
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignCenter)
        # Don't stretch sections to the full viewport; we want the frame to hug the columns.
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.assessments_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d0d0d0;
                border-radius: 0px;
                background: white;
                selection-background-color: transparent;
                selection-color: black;
            }
        """)

        self.table_card = QFrame()
        self.table_card.setObjectName("table_card")
        self.table_card.setStyleSheet(
            "#table_card { border: 1px solid #d0d0d0; border-radius: 8px; background: white; }"
        )
        card_layout = QVBoxLayout(self.table_card)
        card_layout.setContentsMargins(16, 12, 12, 12)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.assessments_table, 1)
        self.table_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.editor_card = QFrame()
        self.editor_card.setObjectName("editor_card")
        self.editor_card.setStyleSheet(
            "#editor_card { border: 1px solid #d0d0d0; border-radius: 8px; background: white; }"
        )
        editor_layout = QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(16, 12, 12, 12)
        self.target_label = QLabel("Target: (none)")
        editor_layout.addWidget(self.target_label)
        editor_layout.addLayout(row)
        editor_layout.addStretch(1)

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
