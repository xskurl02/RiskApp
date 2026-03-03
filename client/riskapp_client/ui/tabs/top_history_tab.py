"""Top history / snapshots tab widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDateTime, QTimer  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
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
        layout.addLayout(row1)

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

        layout.addLayout(row2)

        self.top_report = QLabel("")
        layout.addWidget(self.top_report)

        self.top_table = QTableWidget(0, 6)
        self.top_table.setHorizontalHeaderLabels(
            ["Captured", "Rank", "Title", "P", "I", "Score"]
        )
        self.top_table.verticalHeader().setVisible(False)
        self.top_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.top_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.top_table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.top_table)

        self.setLayout(layout)
