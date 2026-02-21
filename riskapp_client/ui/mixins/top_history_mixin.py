"""MainWindow mixin for snapshot history (“Top history”).

Triggers snapshots (manual/auto) and renders ranked snapshots in the UI.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QDateTime  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

from riskapp_client.services import permissions

class TopHistoryMixin:
    """MainWindow mixin: TopHistoryMixin"""
    def _maybe_auto_snapshot(self) -> None:
        """Take a snapshot automatically if enabled and the interval has elapsed.

        Uses an in-memory per-project throttle (last snapshot timestamp).
        """
        pid = self.current_project_id
        if not pid:
            return

        # Only meaningful online and when the user has manager rights.
        if self._detect_offline_mode():
            return

        if not self.auto_snapshot_chk.isEnabled() or not self.auto_snapshot_chk.isChecked():
            return

        if not permissions.role_at_least(self.current_role, "manager"):
            QMessageBox.information(self, "Not allowed", "You need manager role to create snapshot.")
            return

        days = int(self.auto_snapshot_days.value())
        if days <= 0:
            return

        now = datetime.utcnow()
        last = self._last_auto_snapshot_by_project.get(pid)
        if last is not None:
            if (now - last) < timedelta(days=days):
                return

        # Note: server snapshot captures both risks and opportunities; the kind selector is informational.
        try:
            if hasattr(self.backend, "create_snapshot"):
                self.backend.create_snapshot(pid)  # type: ignore[attr-defined]
        except Exception:
            # Don't spam modal dialogs from a background timer.
            return

        self._last_auto_snapshot_by_project[pid] = now
        self._refresh_top_history()

    def _snapshot_now(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        if not hasattr(self.backend, "create_snapshot"):
            QMessageBox.information(self, "Snapshots", "This backend does not support snapshots.")
            return

        try:
            self.backend.create_snapshot(pid)  # type: ignore[attr-defined]
        except Exception as e:
            QMessageBox.critical(self, "Snapshot failed", str(e))
            return

        self._refresh_top_history()

    def _refresh_top_history(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        if not hasattr(self.backend, "top_history"):
            self.top_table.setRowCount(0)
            if hasattr(self, "top_report"):
                self.top_report.setText("Top history not supported by this backend.")
            return

        # read UI filters
        kind_ui = self.top_kind.currentText().strip().lower() if hasattr(self, "top_kind") else "risks"
        kind = "risks" if kind_ui.startswith("risk") else "opportunities"
        limit = int(self.top_limit.value()) if hasattr(self, "top_limit") else 10

        period = self.top_period.currentText() if hasattr(self, "top_period") else "All"
        from_ts = None
        to_ts = None
        if period != "All":
            from_ts = self._dtedit_to_iso_utc_naive(self.top_from)
            to_ts = self._dtedit_to_iso_utc_naive(self.top_to)

            # safety: swap if user picked reversed range
            if from_ts and to_ts and from_ts > to_ts:
                from_ts, to_ts = to_ts, from_ts

        try:
            batches = self.backend.top_history(  # type: ignore[attr-defined]
                pid,
                kind=kind,
                limit=limit,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        except Exception as e:
            QMessageBox.critical(self, "Top history failed", str(e))
            return

        self.top_table.setRowCount(0)

        total_items = 0
        total_batches = 0

        for b in (batches or []):
            total_batches += 1
            captured_raw = str(b.get("captured_at", ""))
            # small formatting: "YYYY-mm-dd HH:MM:SS"
            captured = captured_raw.replace("T", " ")[:19] if captured_raw else ""

            top = b.get("top") or []
            for idx, item in enumerate(top, start=1):
                total_items += 1
                row = self.top_table.rowCount()
                self.top_table.insertRow(row)

                self.top_table.setItem(row, 0, QTableWidgetItem(captured if idx == 1 else ""))  # reduce repeats
                self.top_table.setItem(row, 1, QTableWidgetItem(str(idx)))
                self.top_table.setItem(row, 2, QTableWidgetItem(str(item.get("title", ""))))

                p = str(item.get("probability", ""))
                i = str(item.get("impact", ""))
                s = str(item.get("score", ""))

                self.top_table.setItem(row, 3, QTableWidgetItem(p))
                self.top_table.setItem(row, 4, QTableWidgetItem(i))
                self.top_table.setItem(row, 5, QTableWidgetItem(s))

                for c in (1, 3, 4, 5):
                    it = self.top_table.item(row, c)
                    if it:
                        it.setTextAlignment(Qt.AlignCenter)

        if hasattr(self, "top_report"):
            self.top_report.setText(
                f"{kind.capitalize()} · Top {limit} · {period}"
                + (f" · {total_batches} snapshot(s) · {total_items} row(s)" if total_batches else " · (no data)")
            )

        self.top_table.resizeColumnsToContents()

    def _on_top_period_changed(self, _text: str) -> None:
        """
        Update the From/To widgets and toggle editability based on selected period.
        """
        period = self.top_period.currentText()
        now = QDateTime.currentDateTime()

        if period == "Last 7 days":
            self.top_to.setDateTime(now)
            self.top_from.setDateTime(now.addDays(-7))
        elif period == "Last 30 days":
            self.top_to.setDateTime(now)
            self.top_from.setDateTime(now.addDays(-30))
        # "All" and "Custom" don't force a range here (Custom uses whatever user picked)

        custom = (period == "Custom")
        self.top_from.setEnabled(custom)
        self.top_to.setEnabled(custom)
