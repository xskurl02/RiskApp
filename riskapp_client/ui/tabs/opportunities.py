"""Opportunities tab widget.

UI construction only; MainWindow supplies behavior via callbacks.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from riskapp_client.ui.widgets import RiskForm, setup_readonly_table


class OpportunitiesTab(QWidget):
    """Opportunities list + editor tab."""

    def __init__(
        self,
        *,
        on_export_csv: Callable[[], None],
        on_refresh: Callable[[], None],
        on_opportunity_clicked: Callable[[int, int], None],
        on_new_opportunity: Callable[[], None],
        on_save_opportunity: Callable[[dict], None],
        on_mark_dirty: Callable[..., None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._on_refresh = on_refresh

        layout = QVBoxLayout()

        # ---- Filters ----
        self.opp_filter_search = QLineEdit()
        self.opp_filter_search.setPlaceholderText("Search title…")

        self.opp_filter_min_score = QSpinBox()
        self.opp_filter_min_score.setRange(0, 25)
        self.opp_filter_min_score.setValue(0)

        self.opp_filter_max_score = QSpinBox()
        self.opp_filter_max_score.setRange(0, 25)
        self.opp_filter_max_score.setValue(25)

        self.opp_filter_status = QComboBox()
        self.opp_filter_status.addItems(["(any)", "concept", "active", "closed", "deleted", "happened"])

        self.opp_filter_category = QLineEdit()
        self.opp_filter_category.setPlaceholderText("Category…")

        self.opp_filter_owner = QLineEdit()
        self.opp_filter_owner.setPlaceholderText("Owner user_id…")

        self.opp_filter_from = QLineEdit()
        self.opp_filter_from.setPlaceholderText("From (YYYY-MM-DD)")

        self.opp_filter_to = QLineEdit()
        self.opp_filter_to.setPlaceholderText("To (YYYY-MM-DD)")

        self.opp_filter_report = QLabel("")
        self.opp_filter_report.setTextFormat(Qt.RichText)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(on_export_csv)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_filters)

        self.opp_filter_search.textChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_min_score.valueChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_max_score.valueChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_status.currentTextChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_category.textChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_owner.textChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_from.textChanged.connect(lambda *_: self._on_refresh())
        self.opp_filter_to.textChanged.connect(lambda *_: self._on_refresh())

        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Search"))
        filters_row.addWidget(self.opp_filter_search, 2)
        filters_row.addWidget(QLabel("Min score"))
        filters_row.addWidget(self.opp_filter_min_score)
        filters_row.addWidget(QLabel("Max score"))
        filters_row.addWidget(self.opp_filter_max_score)
        filters_row.addWidget(QLabel("Status"))
        filters_row.addWidget(self.opp_filter_status)
        filters_row.addWidget(QLabel("Category"))
        filters_row.addWidget(self.opp_filter_category, 1)
        filters_row.addWidget(QLabel("Owner"))
        filters_row.addWidget(self.opp_filter_owner, 1)
        filters_row.addWidget(QLabel("From"))
        filters_row.addWidget(self.opp_filter_from)
        filters_row.addWidget(QLabel("To"))
        filters_row.addWidget(self.opp_filter_to)
        filters_row.addWidget(export_btn)
        filters_row.addWidget(clear_btn)
        filters_row.addStretch(1)
        filters_row.addWidget(self.opp_filter_report)

        layout.addLayout(filters_row)

        self.opps_table = QTableWidget(0, 8)
        self.opps_table.setHorizontalHeaderLabels(
            ["Code", "Title", "Category", "Status", "Owner", "P", "I", "Score"]
        )
        for col in range(self.opps_table.columnCount()):
            item = self.opps_table.horizontalHeaderItem(col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)


        setup_readonly_table(self.opps_table, excel_delegate=True)
        self.opps_table.cellClicked.connect(on_opportunity_clicked)


        self.opp_editor_label = QLabel("Editor (new opportunity)")
        self.opp_form = RiskForm(on_save_opportunity)
        self.new_opp_btn = QPushButton("New opportunity")
        self.new_opp_btn.clicked.connect(on_new_opportunity)

        self.opp_form.title.textEdited.connect(on_mark_dirty)
        self.opp_form.p.valueChanged.connect(on_mark_dirty)
        self.opp_form.impact_cost.valueChanged.connect(on_mark_dirty)
        self.opp_form.impact_time.valueChanged.connect(on_mark_dirty)
        self.opp_form.impact_scope.valueChanged.connect(on_mark_dirty)
        self.opp_form.impact_quality.valueChanged.connect(on_mark_dirty)

        hdr = QHBoxLayout()
        hdr.addWidget(self.opp_editor_label)
        hdr.addStretch(1)
        hdr.addWidget(self.new_opp_btn)

        layout.addWidget(self.opps_table)
        layout.addLayout(hdr)
        layout.addWidget(self.opp_form)

        self.setLayout(layout)

    def clear_filters(self) -> None:
        """Reset all filter widgets to defaults."""
        self.opp_filter_search.setText("")
        self.opp_filter_min_score.setValue(0)
        self.opp_filter_max_score.setValue(25)
        self.opp_filter_status.setCurrentIndex(0)
        self.opp_filter_category.setText("")
        self.opp_filter_owner.setText("")
        self.opp_filter_from.setText("")
        self.opp_filter_to.setText("")
        self._on_refresh()
