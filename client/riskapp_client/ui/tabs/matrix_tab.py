"""Risk/Opportunity matrix tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)  # pylint: disable=no-name-in-module


class MatrixTab(QWidget):
    """Probability x Impact matrix view."""

    def __init__(
        self,
        *,
        on_kind_changed: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Matrix (counts per Probability x Impact)"))

        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["Risks", "Opportunities", "Both"])
        if on_kind_changed:
            self.kind_combo.currentTextChanged.connect(on_kind_changed)
        layout.addWidget(self.kind_combo)

        self.risks_label = QLabel("Risks")
        layout.addWidget(self.risks_label)

        self.risks_matrix_table = QTableWidget(5, 5)
        self.risks_matrix_table.setHorizontalHeaderLabels(
            ["I1", "I2", "I3", "I4", "I5"]
        )
        self.risks_matrix_table.setVerticalHeaderLabels(["P1", "P2", "P3", "P4", "P5"])

        layout.addWidget(self.risks_matrix_table)

        self.opps_label = QLabel("Opportunities")
        layout.addWidget(self.opps_label)

        self.opps_matrix_table = QTableWidget(5, 5)
        self.opps_matrix_table.setHorizontalHeaderLabels(["I1", "I2", "I3", "I4", "I5"])
        self.opps_matrix_table.setVerticalHeaderLabels(["P1", "P2", "P3", "P4", "P5"])

        layout.addWidget(self.opps_matrix_table)
        self.setLayout(layout)

        self.set_kind(self.kind_combo.currentText())

    def set_kind(self, text: str) -> None:
        kind = (text or "Risks").strip().lower()
        if kind == "opportunities":
            self.risks_label.hide()
            self.risks_matrix_table.hide()
            self.opps_label.show()
            self.opps_matrix_table.show()
        elif kind == "both":
            self.risks_label.show()
            self.risks_matrix_table.show()
            self.opps_label.show()
            self.opps_matrix_table.show()
        else:  # risks
            self.risks_label.show()
            self.risks_matrix_table.show()
            self.opps_label.hide()
            self.opps_matrix_table.hide()
