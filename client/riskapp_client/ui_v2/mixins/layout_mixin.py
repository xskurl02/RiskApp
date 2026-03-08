"""MainWindow UI construction with clean attribute mapping."""

from __future__ import annotations
import logging
import qdarktheme
from PySide6.QtWidgets import QApplication, QLabel

from riskapp_client.ui_v2.tabs.actions_tab import ActionsTab
from riskapp_client.ui_v2.tabs.assessments_tab import AssessmentsTab
from riskapp_client.ui_v2.tabs.matrix_tab import MatrixTab
from riskapp_client.ui_v2.tabs.members_tab import MembersTab
from riskapp_client.ui_v2.tabs.opportunities_tab import OpportunitiesTab
from riskapp_client.ui_v2.tabs.risks_tab import RisksTab
from riskapp_client.ui_v2.tabs.top_history_tab import TopHistoryTab
from riskapp_client.ui_v2.ui_main_window_design import Ui_MainWindow

logger = logging.getLogger(__name__)

_RISKS_ALIASES = (
    "filter_search", "filter_min_score", "filter_max_score", "filter_report",
    "filter_status", "filter_category", "filter_owner", "filter_from", "filter_to",
)

_OPPS_ALIASES = (
    "opp_filter_search", "opp_filter_min_score", "opp_filter_max_score",
    "opp_filter_status", "opp_filter_category", "opp_filter_owner",
    "opp_filter_from", "opp_filter_to", "opp_filter_report",
)

class LayoutMixin:
    """Handles the heavy lifting of UI construction and attribute mapping."""

    def _build_ui(self) -> None:
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("RiskApp")

        # --- 1. DIRECT UI MAPPINGS ---
        self.project_list = self.ui.project_list
        self.sync_btn = self.ui.sync_btn

        self.role_status = QLabel("Role: Initializing...")
        self.sync_status = QLabel("Sync: Initializing...")
        self.ui.statusbar.addPermanentWidget(self.role_status)
        self.ui.statusbar.addPermanentWidget(self.sync_status)

        # --- CONTEXT HELP (GLOBAL SHELL) ---
        self.project_list.setToolTip("Select a project to load its data")
        self.sync_btn.setToolTip("Manually synchronize local offline changes with the server")
        self.ui.theme_toggle.setToolTip("Toggle between Dark Mode and Light Mode")
        self.ui.sidebar_list.setToolTip("Navigate between different views and tools for the current project")
        # -----------------------------------

        # --- 2. THEME LOGIC ---
        def apply_theme(is_dark: bool):
            theme = "dark" if is_dark else "light"
            # Force multi-line boxes (QPlainTextEdit) to perfectly match single-line boxes
            # Unify single-line and multi-line backgrounds based on the current theme
            bg_color = "#1e1e1e" if is_dark else "#ffffff"
            
            extra_css = f"""
            QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QComboBox, QDateTimeEdit {{
                background-color: {bg_color};
                border: 1px solid rgba(128, 128, 128, 0.3);
                border-radius: 4px;
            }}
            QTextEdit, QPlainTextEdit {{
                padding: 4px;
            }}
            """
            try:
                qdarktheme.setup_theme(theme, additional_qss=extra_css)
            except AttributeError:
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(qdarktheme.load_stylesheet(theme) + extra_css)

        self.ui.theme_toggle.toggled.connect(apply_theme)
        apply_theme(self.ui.theme_toggle.isChecked())

        def bind(src: object, names: tuple[str, ...], **renamed: str) -> None:
            for name in names:
                setattr(self, name, getattr(src, name))
            for dst, src_name in renamed.items():
                setattr(self, dst, getattr(src, src_name))

        # --- 3. TAB INITIALIZATION ---
        
        # CRITICAL FIX: Clear dummy placeholder pages inserted by Qt Designer!
        while self.ui.main_stacked_widget.count() > 0:
            widget = self.ui.main_stacked_widget.widget(0)
            self.ui.main_stacked_widget.removeWidget(widget)
            widget.deleteLater()

        self.risks_tab = RisksTab(
            on_export_csv=self._export_risks_csv,
            on_refresh=lambda: self._refresh_risks(select_id=self.current_risk_id),
            on_risk_clicked=self._on_risk_clicked,
            on_new_risk=self._start_new_risk,
            on_save_risk=self._save_risk,
            on_delete_item=lambda: logger.info("Delete Risk triggered"),
            on_mark_dirty=self._mark_editor_dirty,
            on_fit_table_card=lambda: self._fit_table_card(),
        )
        self.ui.main_stacked_widget.addWidget(self.risks_tab)
        bind(self.risks_tab, _RISKS_ALIASES, 
             risks_table="table", risk_form="form", new_risk_btn="new_btn", editor_label="editor_label",
             _table_card="table_card", _editor_card="editor_card")

        self.opps_tab = OpportunitiesTab(
            on_export_csv=self._export_opportunities_csv,
            on_refresh=lambda: self._refresh_opportunities(select_id=self.current_opportunity_id),
            on_opportunity_clicked=self._on_opportunity_clicked,
            on_new_opportunity=self._start_new_opportunity,
            on_save_opportunity=self._save_opportunity,
            on_delete_item=lambda: logger.info("Delete Opp triggered"),
            on_mark_dirty=self._mark_opp_editor_dirty,
        )
        self.ui.main_stacked_widget.addWidget(self.opps_tab)
        bind(self.opps_tab, _OPPS_ALIASES, 
             opps_table="table", opp_form="form", new_opp_btn="new_btn", opp_editor_label="editor_label",
             _opp_editor_card="editor_card")

        self.matrix_tab = MatrixTab(on_kind_changed=self._on_matrix_kind_changed)
        self.ui.main_stacked_widget.addWidget(self.matrix_tab)
        self.risks_matrix_table = self.matrix_tab.risks_matrix_table
        self.opps_matrix_table = self.matrix_tab.opps_matrix_table

        self.top_tab = TopHistoryTab(
            on_snapshot_now=self._snapshot_now, on_refresh_history=self._refresh_top_history,
            on_period_changed=self._on_top_period_changed, on_maybe_auto_snapshot=self._maybe_auto_snapshot,
        )
        self.ui.main_stacked_widget.addWidget(self.top_tab)

        self.actions_tab = ActionsTab(
            on_action_clicked=self._on_action_clicked, on_save_action=self._save_action,
            on_new_action=self._start_new_action, on_target_type_changed=lambda _: self._toggle_action_target_inputs(),
        )
        self.ui.main_stacked_widget.addWidget(self.actions_tab)

        self.assessments_tab = AssessmentsTab(on_save_assessment=self._save_assessment)
        self.ui.main_stacked_widget.addWidget(self.assessments_tab)

        self.members_tab = MembersTab(
            on_add_or_update_member=self._add_or_update_member, on_remove_selected_member=self._remove_selected_member,
            on_refresh_members=self._refresh_members, on_member_selected=self._on_member_selected,
        )
        self.ui.main_stacked_widget.addWidget(self.members_tab)

        # --- 4. NAVIGATION CONNECTIONS ---
        
        # 1. Manually insert the navigation labels (1:1 with stacked widget inserts above)
        self.ui.sidebar_list.clear()
        self.ui.sidebar_list.addItems([
            "Risks", "Opportunities", "Matrix", "Top history", 
            "Actions", "Assessments", "Members"
        ])

        # 2. Core connections
        self.project_list.itemSelectionChanged.connect(self._on_project_selected)
        self.ui.sidebar_list.currentRowChanged.connect(self.ui.main_stacked_widget.setCurrentIndex)
        self.sync_btn.clicked.connect(self._sync_now)

        # 3. Initialize Top History state
        if hasattr(self.top_tab, 'top_period'):
            self._on_top_period_changed(self.top_tab.top_period.currentText())

        # 4. Force selection of the Risks tab
        self.ui.sidebar_list.setCurrentRow(0)

        app = QApplication.instance()
        if app:
            app.installEventFilter(self)