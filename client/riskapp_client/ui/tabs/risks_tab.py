"""Risks tab widget.

This module contains the Qt UI construction for the Risks tab.
Thin wrapper around the shared ScoredEntitiesTab.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget  # pylint: disable=no-name-in-module

from riskapp_client.ui.tabs.scored_entities_base_tab import ScoredEntitiesTab


class RisksTab(ScoredEntitiesTab):
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
        super().__init__(
            entity_label_singular="risk",
            on_export_csv=on_export_csv,
            on_refresh=on_refresh,
            on_item_clicked=on_risk_clicked,
            on_new_item=on_new_risk,
            on_save_item=on_save_risk,
            on_mark_dirty=on_mark_dirty,
            on_fit_table_card=on_fit_table_card,
            parent=parent,
        )

        # Back-compat attribute names used by LayoutMixin and mixins.
        self.risks_table = self.table
        self.risk_form = self.form
        self.new_risk_btn = self.new_btn
