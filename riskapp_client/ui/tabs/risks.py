"""Risks tab widget.

This module contains the Qt UI construction for the Risks tab.
Behavior remains in MainWindow via injected callbacks.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from riskapp_client.ui.widgets import CrispHeader, RiskForm, setup_readonly_table


class RisksTab(QWidget):
    """Risks list + editor tab."""

    def __init__(
        self,
        *,
        on_export_csv: Callable[[], None],
        on_refresh: Callable[[], None],
        on_risk_clicked: Callable[[int, int], None],
        on_new_risk: Callable[[], None],
        on_save_risk: Callable[[dict], None],
        on_mark_dirty: Callable[..., None],
        on_fit_table_card: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._on_refresh = on_refresh

        layout = QVBoxLayout()

        # ---- Filters + tiny report ----
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText("Search title…")

        self.filter_min_score = QSpinBox()
        self.filter_min_score.setRange(0, 25)
        self.filter_min_score.setValue(0)

        self.filter_max_score = QSpinBox()
        self.filter_max_score.setRange(0, 25)
        self.filter_max_score.setValue(25)

        self.filter_report = QLabel("")
        self.filter_report.setTextFormat(Qt.RichText)

        self.filter_status = QComboBox()
        self.filter_status.addItems(["(any)", "concept", "active", "closed", "deleted", "happened"])

        self.filter_category = QLineEdit()
        self.filter_category.setPlaceholderText("Category…")

        self.filter_owner = QLineEdit()
        self.filter_owner.setPlaceholderText("Owner user_id…")

        self.filter_from = QLineEdit()
        self.filter_from.setPlaceholderText("From (YYYY-MM-DD)")

        self.filter_to = QLineEdit()
        self.filter_to.setPlaceholderText("To (YYYY-MM-DD)")

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(on_export_csv)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_filters)

        # refresh on any change
        self.filter_search.textChanged.connect(lambda *_: self._on_refresh())
        self.filter_min_score.valueChanged.connect(lambda *_: self._on_refresh())
        self.filter_max_score.valueChanged.connect(lambda *_: self._on_refresh())
        self.filter_status.currentTextChanged.connect(lambda *_: self._on_refresh())
        self.filter_category.textChanged.connect(lambda *_: self._on_refresh())
        self.filter_owner.textChanged.connect(lambda *_: self._on_refresh())
        self.filter_from.textChanged.connect(lambda *_: self._on_refresh())
        self.filter_to.textChanged.connect(lambda *_: self._on_refresh())

        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Search"))
        filters_row.addWidget(self.filter_search, 2)
        filters_row.addWidget(QLabel("Min score"))
        filters_row.addWidget(self.filter_min_score)
        filters_row.addWidget(QLabel("Max score"))
        filters_row.addWidget(self.filter_max_score)
        filters_row.addWidget(QLabel("Status"))
        filters_row.addWidget(self.filter_status)
        filters_row.addWidget(QLabel("Category"))
        filters_row.addWidget(self.filter_category, 1)
        filters_row.addWidget(QLabel("Owner"))
        filters_row.addWidget(self.filter_owner, 1)
        filters_row.addWidget(QLabel("From"))
        filters_row.addWidget(self.filter_from)
        filters_row.addWidget(QLabel("To"))
        filters_row.addWidget(self.filter_to)
        filters_row.addWidget(export_btn)
        filters_row.addWidget(clear_btn)
        filters_row.addStretch(1)
        filters_row.addWidget(self.filter_report)

        layout.addLayout(filters_row)

        self.risks_table = QTableWidget(0, 8)
        self.risks_table.setHorizontalHeaderLabels(
            ["Code", "Title", "Category", "Status", "Owner", "P", "I", "Score"]
        )
        for col in range(self.risks_table.columnCount()):
            item = self.risks_table.horizontalHeaderItem(col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)

        self.risks_table.cellClicked.connect(on_risk_clicked)

        setup_readonly_table(self.risks_table, excel_delegate=True)
        self.risks_table.setMouseTracking(True)
        self.risks_table.viewport().setMouseTracking(True)

        self.risks_table.setFrameShape(QFrame.Box)
        self.risks_table.setFrameShadow(QFrame.Plain)
        self.risks_table.setLineWidth(0)
        self.risks_table.setMidLineWidth(0)

        self.risks_table.setHorizontalHeader(
            CrispHeader(Qt.Horizontal, self.risks_table, line_color="#d0d0d0")
        )

        hh = self.risks_table.horizontalHeader()
        hh.setSectionsClickable(False)
        hh.setHighlightSections(False)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setDefaultAlignment(Qt.AlignCenter)

        self.risks_table.verticalHeader().setVisible(False)
        self.risks_table.setCornerButtonEnabled(False)

        self.risks_table.setShowGrid(False)
        self.risks_table.setStyleSheet(
            """
            QTableWidget {
                border: 1px solid #d0d0d0;
                border-radius: 0px;
                background: white;
                selection-background-color: transparent;
                selection-color: black;
            }
            """
        )
        # delegate is set by setup_readonly_table(...)

        self.table_card = QFrame()
        self.table_card.setObjectName("table_card")
        self.table_card.setAttribute(Qt.WA_StyledBackground, True)

        hh.sectionResized.connect(lambda *_: on_fit_table_card())

        card_layout = QHBoxLayout(self.table_card)
        card_layout.setContentsMargins(16, 12, 12, 12)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.risks_table, 0, Qt.AlignLeft | Qt.AlignTop)
        card_layout.addStretch(1)

        self.table_card.setStyleSheet(
            """
            #table_card {
                border: 1px solid #d0d0d0;
                background: white;
                border-radius: 8px;
            }
            """
        )
        self.table_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Editor widgets
        self.editor_label = QLabel("Editor (new risk)")
        self.risk_form = RiskForm(on_save_risk)
        self.new_risk_btn = QPushButton("New risk")
        self.new_risk_btn.clicked.connect(on_new_risk)

        # dirty tracking hooks
        self.risk_form.title.textEdited.connect(on_mark_dirty)
        self.risk_form.p.valueChanged.connect(on_mark_dirty)
        self.risk_form.impact_cost.valueChanged.connect(on_mark_dirty)
        self.risk_form.impact_time.valueChanged.connect(on_mark_dirty)
        self.risk_form.impact_scope.valueChanged.connect(on_mark_dirty)
        self.risk_form.impact_quality.valueChanged.connect(on_mark_dirty)

        self.editor_card = QFrame()
        self.editor_card.setObjectName("editor_card")
        self.editor_card.setStyleSheet(
            """
            #editor_card {
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                background: white;
            }
            """
        )
        self.editor_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        editor_layout = QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(16, 12, 12, 12)
        editor_layout.setSpacing(10)

        hdr = QHBoxLayout()
        hdr.addWidget(self.editor_label)
        hdr.addStretch(1)
        hdr.addWidget(self.new_risk_btn)

        editor_layout.addLayout(hdr)
        editor_layout.addWidget(self.risk_form)
        self.editor_card.setFixedHeight(self.editor_card.sizeHint().height())

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(5)
        split.addWidget(self.table_card)
        split.addWidget(self.editor_card)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([600, 240])

        split.setStyleSheet(
            """
            QSplitter::handle:horizontal {
                background: transparent;
                border: none;
                margin: 0px;
            }
            """
        )
        split.handle(1).setAttribute(Qt.WA_StyledBackground, True)
        split.handle(1).setStyleSheet("background: transparent; border: none;")

        layout.addWidget(split)
        self.setLayout(layout)

    def clear_filters(self) -> None:
        """Reset all filter widgets to defaults."""
        self.filter_search.setText("")
        self.filter_min_score.setValue(0)
        self.filter_max_score.setValue(25)
        self.filter_status.setCurrentIndex(0)
        self.filter_category.setText("")
        self.filter_owner.setText("")
        self.filter_from.setText("")
        self.filter_to.setText("")
        self._on_refresh()
