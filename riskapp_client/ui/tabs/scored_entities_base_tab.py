"""Shared scored-entity tab (Risks / Opportunities).

This centralizes the duplicate UI for scored entities (filters + table + editor).
Behavior is still supplied by MainWindow via callbacks.
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

from riskapp_client.domain.scored_entity_fields import ALL_STATUSES
from riskapp_client.services.entity_filters import ANY_STATUS
from riskapp_client.ui.components.custom_gui_widgets import CrispHeader, RiskForm, setup_readonly_table

MAX_SCORE_UI = 25


class ScoredEntitiesTab(QWidget):
    """Generic list + editor tab for scored entities."""

    def __init__(
        self,
        *,
        entity_label_singular: str,
        on_export_csv: Callable[[], None],
        on_refresh: Callable[[], None],
        on_item_clicked: Callable[[int, int], None],
        on_new_item: Callable[[], None],
        on_save_item: Callable[[dict], None],
        on_mark_dirty: Callable[..., None],
        on_fit_table_card: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._on_refresh = on_refresh

        layout = QVBoxLayout()

        # ---- Filters + tiny report ----
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText("Search title…")

        self.filter_min_score = QSpinBox()
        self.filter_min_score.setRange(0, MAX_SCORE_UI)
        self.filter_min_score.setValue(0)

        self.filter_max_score = QSpinBox()
        self.filter_max_score.setRange(0, MAX_SCORE_UI)
        self.filter_max_score.setValue(MAX_SCORE_UI)

        self.filter_report = QLabel("")
        self.filter_report.setTextFormat(Qt.RichText)

        self.filter_status = QComboBox()
        self.filter_status.addItems([ANY_STATUS, *ALL_STATUSES])

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
        for w in (self.filter_search, self.filter_category, self.filter_owner, self.filter_from, self.filter_to):
            w.textChanged.connect(lambda *_: self._on_refresh())
        for w in (self.filter_min_score, self.filter_max_score):
            w.valueChanged.connect(lambda *_: self._on_refresh())
        self.filter_status.currentTextChanged.connect(lambda *_: self._on_refresh())

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

        # ---- Table ----
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Code", "Title", "Category", "Status", "Owner", "P", "I", "Score"]
        )
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)

        self.table.cellClicked.connect(on_item_clicked)

        setup_readonly_table(self.table, excel_delegate=True)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)

        self.table.setFrameShape(QFrame.Box)
        self.table.setFrameShadow(QFrame.Plain)
        self.table.setLineWidth(0)
        self.table.setMidLineWidth(0)

        self.table.setHorizontalHeader(
            CrispHeader(Qt.Horizontal, self.table, line_color="#d0d0d0")
        )

        hh = self.table.horizontalHeader()
        hh.setSectionsClickable(False)
        hh.setHighlightSections(False)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setDefaultAlignment(Qt.AlignCenter)

        self.table.verticalHeader().setVisible(False)
        self.table.setCornerButtonEnabled(False)

        self.table.setShowGrid(False)
        self.table.setStyleSheet(
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

        self.table_card = QFrame()
        self.table_card.setObjectName("table_card")
        self.table_card.setAttribute(Qt.WA_StyledBackground, True)

        if on_fit_table_card:
            hh.sectionResized.connect(lambda *_: on_fit_table_card())

        card_layout = QHBoxLayout(self.table_card)
        card_layout.setContentsMargins(16, 12, 12, 12)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.table, 0, Qt.AlignLeft | Qt.AlignTop)
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

        # ---- Editor ----
        self.editor_label = QLabel(f"Editor (new {entity_label_singular})")
        self.form = RiskForm(on_save_item)
        self.new_btn = QPushButton(f"New {entity_label_singular}")
        self.new_btn.clicked.connect(on_new_item)

        # dirty tracking hooks
        self.form.title.textEdited.connect(on_mark_dirty)
        self.form.p.valueChanged.connect(on_mark_dirty)
        self.form.impact_cost.valueChanged.connect(on_mark_dirty)
        self.form.impact_time.valueChanged.connect(on_mark_dirty)
        self.form.impact_scope.valueChanged.connect(on_mark_dirty)
        self.form.impact_quality.valueChanged.connect(on_mark_dirty)

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
        hdr.addWidget(self.new_btn)

        editor_layout.addLayout(hdr)
        editor_layout.addWidget(self.form)
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
        self.filter_max_score.setValue(self.filter_max_score.maximum())
        self.filter_status.setCurrentIndex(0)
        self.filter_category.setText("")
        self.filter_owner.setText("")
        self.filter_from.setText("")
        self.filter_to.setText("")
        self._on_refresh()
