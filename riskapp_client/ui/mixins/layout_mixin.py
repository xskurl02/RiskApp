"""MainWindow UI construction.

Builds the Qt layout and wires tab widgets to mixin callbacks.
"""
from __future__ import annotations

from PySide6.QtCore import Qt  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from riskapp_client.ui.tabs.actions import ActionsTab
from riskapp_client.ui.tabs.assessments import AssessmentsTab
from riskapp_client.ui.tabs.matrix import MatrixTab
from riskapp_client.ui.tabs.members import MembersTab
from riskapp_client.ui.tabs.opportunities import OpportunitiesTab
from riskapp_client.ui.tabs.risks import RisksTab
from riskapp_client.ui.tabs.top_history import TopHistoryTab

class LayoutMixin:
    """MainWindow mixin: LayoutMixin"""
    def _build_ui(self) -> None:
        """Construct all Qt widgets and wire callbacks."""
        self.setWindowTitle("RiskApp")
        self.resize(1000, 650)

        root = QWidget()
        root_layout = QHBoxLayout()

        # Left: Projects
        left = QVBoxLayout()
        left.addWidget(QLabel("Projects"))
        self.project_list = QListWidget()
        self.project_list.itemSelectionChanged.connect(self._on_project_selected)
        left.addWidget(self.project_list)

        self.sync_status = QLabel("")
        self.role_status = QLabel("Role: (unknown)")
        self.sync_btn = QPushButton("Sync now")
        self.sync_btn.clicked.connect(self._sync_now)
        left.addWidget(self.sync_status)
        left.addWidget(self.role_status)
        left.addWidget(self.sync_btn)

        # Right: Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabWidget::panel {
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: white;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                padding: 8px 14px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }
            QTabBar::tab:selected {
                background: #e6e6e6;
            }
            QTabWidget::tab-bar {
                left: 5px;
            }
            """
        )

        # Tab: Risks
        self.risks_tab = RisksTab(
            on_export_csv=self._export_risks_csv,
            on_refresh=lambda: self._refresh_risks(select_risk_id=self.current_risk_id),
            on_risk_clicked=self._on_risk_clicked,
            on_new_risk=self._start_new_risk,
            on_save_risk=self._save_risk,
            on_mark_dirty=self._mark_editor_dirty,
            on_fit_table_card=lambda: self._fit_table_card(),
        )
        self.tabs.addTab(self.risks_tab, "Risks")

        # Backward-compatible attribute aliases (existing methods expect these names)
        self.filter_search = self.risks_tab.filter_search
        self.filter_min_score = self.risks_tab.filter_min_score
        self.filter_max_score = self.risks_tab.filter_max_score
        self.filter_report = self.risks_tab.filter_report
        self.filter_status = self.risks_tab.filter_status
        self.filter_category = self.risks_tab.filter_category
        self.filter_owner = self.risks_tab.filter_owner
        self.filter_from = self.risks_tab.filter_from
        self.filter_to = self.risks_tab.filter_to
        self.risks_table = self.risks_tab.risks_table
        self.risk_form = self.risks_tab.risk_form
        self.new_risk_btn = self.risks_tab.new_risk_btn
        self.editor_label = self.risks_tab.editor_label
        self._table_card = self.risks_tab.table_card
        self._editor_card = self.risks_tab.editor_card

        # Tab: Opportunities
        self.opps_tab = OpportunitiesTab(
            on_export_csv=self._export_opportunities_csv,
            on_refresh=lambda: self._refresh_opportunities(select_id=self.current_opportunity_id),
            on_opportunity_clicked=self._on_opportunity_clicked,
            on_new_opportunity=self._start_new_opportunity,
            on_save_opportunity=self._save_opportunity,
            on_mark_dirty=lambda *_: setattr(self, "_opp_editor_dirty", True),
        )
        self.tabs.addTab(self.opps_tab, "Opportunities")

        self.opp_filter_search = self.opps_tab.opp_filter_search
        self.opp_filter_min_score = self.opps_tab.opp_filter_min_score
        self.opp_filter_max_score = self.opps_tab.opp_filter_max_score
        self.opp_filter_status = self.opps_tab.opp_filter_status
        self.opp_filter_category = self.opps_tab.opp_filter_category
        self.opp_filter_owner = self.opps_tab.opp_filter_owner
        self.opp_filter_from = self.opps_tab.opp_filter_from
        self.opp_filter_to = self.opps_tab.opp_filter_to
        self.opp_filter_report = self.opps_tab.opp_filter_report
        self.opps_table = self.opps_tab.opps_table
        self.opp_editor_label = self.opps_tab.opp_editor_label
        self.opp_form = self.opps_tab.opp_form
        self.new_opp_btn = self.opps_tab.new_opp_btn

        # Tab: Matrix
        self.matrix_tab = MatrixTab()
        self.tabs.addTab(self.matrix_tab, "Matrix")
        self.matrix_table = self.matrix_tab.matrix_table

        # Tab: Top history
        self.top_tab = TopHistoryTab(
            on_snapshot_now=self._snapshot_now,
            on_refresh_history=self._refresh_top_history,
            on_period_changed=self._on_top_period_changed,
            on_maybe_auto_snapshot=self._maybe_auto_snapshot,
        )
        self.tabs.addTab(self.top_tab, "Top history")

        self.snapshot_btn = self.top_tab.snapshot_btn
        self.auto_snapshot_chk = self.top_tab.auto_snapshot_chk
        self.auto_snapshot_kind = self.top_tab.auto_snapshot_kind
        self.auto_snapshot_days = self.top_tab.auto_snapshot_days
        self._auto_snap_timer = self.top_tab.auto_snap_timer
        self.top_kind = self.top_tab.top_kind
        self.top_limit = self.top_tab.top_limit
        self.top_period = self.top_tab.top_period
        self.top_from = self.top_tab.top_from
        self.top_to = self.top_tab.top_to
        self.refresh_top_btn = self.top_tab.refresh_top_btn
        self.top_report = self.top_tab.top_report
        self.top_table = self.top_tab.top_table

        # Ensure period selection initializes from/to range + disables edits when not Custom.
        self._on_top_period_changed(self.top_period.currentText())

        # Tab: Actions
        self.actions_tab = ActionsTab(
            on_action_clicked=self._on_action_clicked,
            on_save_action=self._save_action,
            on_new_action=self._start_new_action,
            on_target_type_changed=lambda _text: self._toggle_action_target_inputs(),
        )
        self.tabs.addTab(self.actions_tab, "Actions")

        self.actions_table = self.actions_tab.actions_table
        self.action_editor_label = self.actions_tab.action_editor_label
        self.action_target_type = self.actions_tab.action_target_type
        self.action_risk_combo = self.actions_tab.action_risk_combo
        self.action_opp_combo = self.actions_tab.action_opp_combo
        self.action_kind = self.actions_tab.action_kind
        self.action_status = self.actions_tab.action_status
        self.action_title = self.actions_tab.action_title
        self.action_desc = self.actions_tab.action_desc
        self.action_owner = self.actions_tab.action_owner
        self.action_save_btn = self.actions_tab.action_save_btn
        self.action_new_btn = self.actions_tab.action_new_btn

        # Tab: Assessments
        self.assessments_tab = AssessmentsTab(on_save_assessment=self._save_assessment)
        self.tabs.addTab(self.assessments_tab, "Assessments")

        self.assess_p = self.assessments_tab.assess_p
        self.assess_i = self.assessments_tab.assess_i
        self.assess_notes = self.assessments_tab.assess_notes
        self.assess_save_btn = self.assessments_tab.assess_save_btn
        self.assessments_table = self.assessments_tab.assessments_table

        # Tab: Members
        self.members_tab = MembersTab(
            on_add_or_update_member=self._add_or_update_member,
            on_remove_selected_member=self._remove_selected_member,
            on_refresh_members=self._refresh_members,
            on_member_selected=self._on_member_selected,
        )
        self.tabs.addTab(self.members_tab, "Members")

        self.members_hint = self.members_tab.members_hint
        self.member_email = self.members_tab.member_email
        self.member_role = self.members_tab.member_role
        self.member_add_btn = self.members_tab.member_add_btn
        self.member_remove_btn = self.members_tab.member_remove_btn
        self.member_refresh_btn = self.members_tab.member_refresh_btn
        self.members_table = self.members_tab.members_table

        # Layout polish
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)
        self.risks_tab.layout().setContentsMargins(8, 8, 8, 8)
        self.risks_tab.layout().setSpacing(8)
        self.matrix_tab.layout().setContentsMargins(8, 8, 8, 8)
        self.matrix_tab.layout().setSpacing(8)

        root_layout.addLayout(left, 1)
        root_layout.addWidget(self.tabs, 3)

        root.setLayout(root_layout)
        self.setCentralWidget(root)

        QApplication.instance().installEventFilter(self)
        self._load_projects()
