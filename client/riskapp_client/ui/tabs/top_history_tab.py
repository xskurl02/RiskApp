"""Top history / snapshots tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDateTime, Qt, QTimer  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from riskapp_client.ui.components.custom_gui_widgets import (
    CrispHeader,
    setup_readonly_table,
)


class TopHistoryTab(QWidget):
    """Top history (snapshots) tab."""

    def __init__(
        self,
        *,
        on_snapshot_now: Callable[[], None],
        on_refresh_history: Callable[[], None],
        on_period_changed: Callable[[str], None],
        on_maybe_auto_snapshot: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self.snapshot_btn = QPushButton("Take snapshot now")
        self.snapshot_btn.clicked.connect(on_snapshot_now)

        self.auto_snapshot_chk = QCheckBox("Auto snapshot")
        self.auto_snapshot_kind = QComboBox()
        self.auto_snapshot_kind.addItems(["Risks", "Opportunities", "Both"])
        self.auto_snapshot_days = QSpinBox()
        self.auto_snapshot_days.setRange(1, 365)
        self.auto_snapshot_days.setValue(7)

        row1.addWidget(self.snapshot_btn)
        row1.addWidget(self.auto_snapshot_chk)
        row1.addWidget(QLabel("Every"))
        row1.addWidget(self.auto_snapshot_days)
        row1.addWidget(QLabel("day(s)"))
        row1.addWidget(QLabel("Kind"))
        row1.addWidget(self.auto_snapshot_kind)

        self.auto_snap_timer = QTimer(self)
        self.auto_snap_timer.setInterval(60 * 60 * 1000)
        self.auto_snap_timer.timeout.connect(on_maybe_auto_snapshot)
        self.auto_snap_timer.start()

        row1.addStretch(1)

        row2 = QHBoxLayout()

        self.top_kind = QComboBox()
        self.top_kind.addItems(["Risks", "Opportunities"])
        self.top_kind.setCurrentText("Risks")

        self.top_limit = QSpinBox()
        self.top_limit.setRange(1, 100)
        self.top_limit.setValue(10)

        self.top_period = QComboBox()
        self.top_period.addItems(["All", "Last 7 days", "Last 30 days", "Custom"])
        self.top_period.setCurrentText("Last 30 days")

        self.top_from = QDateTimeEdit()
        self.top_to = QDateTimeEdit()
        self.top_from.setCalendarPopup(True)
        self.top_to.setCalendarPopup(True)
        self.top_from.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.top_to.setDisplayFormat("yyyy-MM-dd HH:mm")

        now = QDateTime.currentDateTime()
        self.top_to.setDateTime(now)
        self.top_from.setDateTime(now.addDays(-30))

        self.refresh_top_btn = QPushButton("Refresh history")
        self.refresh_top_btn.clicked.connect(on_refresh_history)

        self.top_period.currentTextChanged.connect(on_period_changed)

        row2.addWidget(QLabel("Kind"))
        row2.addWidget(self.top_kind)
        row2.addWidget(QLabel("Top N"))
        row2.addWidget(self.top_limit)
        row2.addWidget(QLabel("Period"))
        row2.addWidget(self.top_period)
        row2.addWidget(QLabel("From"))
        row2.addWidget(self.top_from)
        row2.addWidget(QLabel("To"))
        row2.addWidget(self.top_to)
        row2.addWidget(self.refresh_top_btn)
        row2.addStretch(1)

        self.top_report = QLabel("")

        self.top_table = QTableWidget(0, 6)
        self.top_table.setHorizontalHeaderLabels(
            ["Captured", "Rank", "Title", "P", "I", "Score"]
        )

        # --- Apply crisp styling + expansion behavior (match Risks/Opportunities) ---
        setup_readonly_table(self.top_table)
        self.top_table.setHorizontalHeader(
            CrispHeader(Qt.Horizontal, self.top_table, line_color="#d0d0d0")
        )
        hh = self.top_table.horizontalHeader()
        hh.setSectionsClickable(False)
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setStretchLastSection(True)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        # Let Title absorb remaining space so the table fills the card instead of becoming a small box.
        hh.setSectionResizeMode(2, QHeaderView.Stretch)

        self.top_table.verticalHeader().setVisible(False)
        self.top_table.setCornerButtonEnabled(False)
        self.top_table.setShowGrid(False)
        self.top_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.top_table.setStyleSheet("""
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
        card_layout.addWidget(self.top_table, 1)
        self.table_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.editor_card = QFrame()
        self.editor_card.setObjectName("editor_card")
        self.editor_card.setStyleSheet(
            "#editor_card { border: 1px solid #d0d0d0; border-radius: 8px; background: white; }"
        )
        editor_layout = QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(16, 12, 12, 12)
        editor_layout.addLayout(row1)
        editor_layout.addLayout(row2)
        editor_layout.addWidget(self.top_report)
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
