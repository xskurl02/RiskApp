"""Risk matrix tab widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QVBoxLayout, QWidget  # pylint: disable=no-name-in-module


class MatrixTab(QWidget):
    """Probability x Impact matrix view."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Risk matrix (counts per Probability x Impact)"))

        self.matrix_table = QTableWidget(5, 5)
        self.matrix_table.setHorizontalHeaderLabels(["I1", "I2", "I3", "I4", "I5"])
        self.matrix_table.setVerticalHeaderLabels(["P1", "P2", "P3", "P4", "P5"])

        layout.addWidget(self.matrix_table)
        self.setLayout(layout)
