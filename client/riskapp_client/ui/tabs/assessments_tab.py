"""Assessments tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


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

        self.target_label = QLabel("Target: (none)")
        layout.addWidget(self.target_label)

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

        layout.addLayout(row)

        self.assessments_table = QTableWidget(0, 6)
        self.assessments_table.setHorizontalHeaderLabels(
            ["Assessor", "P", "I", "Score", "Notes", "Updated"]
        )
        self.assessments_table.verticalHeader().setVisible(False)
        self.assessments_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.assessments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.assessments_table.setSelectionMode(QAbstractItemView.SingleSelection)

        layout.addWidget(self.assessments_table)
        self.setLayout(layout)
