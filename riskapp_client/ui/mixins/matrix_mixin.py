"""MainWindow mixin for the risk matrix view.

Computes and renders a 5×5 count matrix from current risks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem  # pylint: disable=no-name-in-module

class MatrixMixin:
    """MainWindow mixin: MatrixMixin"""
    def _refresh_matrix(self) -> None:
        pid = self.current_project_id
        if not pid:
            return

        try:
            risks = self.backend.list_risks(pid)
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))
            return

        grid = [[0 for _ in range(5)] for __ in range(5)]
        for r in risks:
            p = max(1, min(5, r.probability))
            i = max(1, min(5, r.impact))
            grid[p - 1][i - 1] += 1

        for rp in range(5):
            for ci in range(5):
                it = QTableWidgetItem(str(grid[rp][ci]))
                it.setTextAlignment(Qt.AlignCenter)
                self.matrix_table.setItem(rp, ci, it)

        self.matrix_table.resizeColumnsToContents()
