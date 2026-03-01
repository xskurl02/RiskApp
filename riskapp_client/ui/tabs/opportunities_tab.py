"""Opportunities tab widget.

Thin wrapper around the shared ScoredEntitiesTab.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget  # pylint: disable=no-name-in-module


from riskapp_client.ui.tabs.scored_entities_base_tab import ScoredEntitiesTab


class OpportunitiesTab(ScoredEntitiesTab):
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
        super().__init__(
            entity_label_singular="opportunity",
            on_export_csv=on_export_csv,
            on_refresh=on_refresh,
            on_item_clicked=on_opportunity_clicked,
            on_new_item=on_new_opportunity,
            on_save_item=on_save_opportunity,
            on_mark_dirty=on_mark_dirty,
            on_fit_table_card=None,
            parent=parent,
        )

        # Back-compat attribute names used by LayoutMixin and mixins.
        self.opps_table = self.table
        self.opp_form = self.form
        self.new_opp_btn = self.new_btn
        self.opp_editor_label = self.editor_label

        # Back-compat filter widget names for the OpportunitiesMixin.
        self.opp_filter_search = self.filter_search
        self.opp_filter_min_score = self.filter_min_score
        self.opp_filter_max_score = self.filter_max_score
        self.opp_filter_status = self.filter_status
        self.opp_filter_category = self.filter_category
        self.opp_filter_owner = self.filter_owner
        self.opp_filter_from = self.filter_from
        self.opp_filter_to = self.filter_to
        self.opp_filter_report = self.filter_report