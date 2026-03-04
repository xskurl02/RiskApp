"""Risk/Opportunity matrix tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QComboBox,
    QFrame,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)  # pylint: disable=no-name-in-module
from riskapp_client.ui.components.custom_gui_widgets import CrispHeader, setup_readonly_table

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


        def style_matrix(table: QTableWidget) -> None:
            setup_readonly_table(table)
            table.setFrameShape(QFrame.Box)
            table.setFrameShadow(QFrame.Plain)
            table.setLineWidth(0)
            
            table.setHorizontalHeader(CrispHeader(Qt.Horizontal, table, line_color="#d0d0d0"))
            hh = table.horizontalHeader()
            hh.setSectionsClickable(False)
            hh.setHighlightSections(False)
            hh.setSectionResizeMode(QHeaderView.Fixed)
            hh.setDefaultSectionSize(70)

            vh = table.verticalHeader()
            vh.setVisible(True)
            vh.setSectionsClickable(False)
            vh.setHighlightSections(False)
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(50)
            vh.setDefaultAlignment(Qt.AlignCenter)

            # Shrink-wrap the table border perfectly around the cells
            table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
            table.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

            table.setCornerButtonEnabled(True)
            table.setShowGrid(True)
            table.setStyleSheet("""
                QTableWidget {
                    border: 1px solid #d0d0d0;
                    border-radius: 0px;
                    background: white;
                    gridline-color: #d0d0d0;
                    selection-background-color: transparent;
                    selection-color: black;
                }
                QTableCornerButton::section {
                    background-color: #f5f5f5;
                    border: none;
                    border-bottom: 1px solid #d0d0d0;
                    border-right: 1px solid #d0d0d0;
                }
            """)

        style_matrix(self.risks_matrix_table)


        layout.addWidget(self.risks_matrix_table)

        self.opps_label = QLabel("Opportunities")
        layout.addWidget(self.opps_label)

        self.opps_matrix_table = QTableWidget(5, 5)
        self.opps_matrix_table.setHorizontalHeaderLabels(["I1", "I2", "I3", "I4", "I5"])
        self.opps_matrix_table.setVerticalHeaderLabels(["P1", "P2", "P3", "P4", "P5"])
        style_matrix(self.opps_matrix_table)

        layout.addWidget(self.opps_matrix_table)

        # Push everything to the top so tables don't stretch vertically across the whole screen
        layout.addStretch(1)        
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
