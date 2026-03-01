"""MainWindow mixin for the risk matrix view.

Computes and renders a 5×5 count matrix from current risks.
"""

from __future__ import annotations

class MatrixMixin:
    """MainWindow mixin: MatrixMixin"""

    def _refresh_matrix(self) -> None:
        pid = self.current_project_id
        if not pid:
            return
        risks = self._call_backend("Backend error", self.backend.list_risks, pid)
        if risks is None:
            return

        grid = [[0 for _ in range(5)] for __ in range(5)]
        for r in risks:
            p = max(1, min(5, r.probability))
            i = max(1, min(5, r.impact))
            grid[p - 1][i - 1] += 1

        for rp in range(5):
            for ci in range(5):
                self.matrix_table.setItem(rp, ci, self._mk_item(str(grid[rp][ci]), align_center=True))

        self.matrix_table.resizeColumnsToContents()
