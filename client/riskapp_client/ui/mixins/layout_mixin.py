"""MainWindow UI construction.

Builds the Qt layout and wires tab widgets to mixin callbacks.

To minimize churn, tab widget attributes are bound onto the MainWindow via small
name-lists instead of dozens of one-off assignments.
"""

from __future__ import annotations

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
from riskapp_client.ui.tabs.actions_tab import ActionsTab
from riskapp_client.ui.tabs.assessments_tab import AssessmentsTab
from riskapp_client.ui.tabs.matrix_tab import MatrixTab
from riskapp_client.ui.tabs.members_tab import MembersTab
from riskapp_client.ui.tabs.opportunities_tab import OpportunitiesTab
from riskapp_client.ui.tabs.risks_tab import RisksTab
from riskapp_client.ui.tabs.top_history_tab import TopHistoryTab

_RISKS_ALIASES = (
    "filter_search",
    "filter_min_score",
    "filter_max_score",
    "filter_report",
    "filter_status",
    "filter_category",
    "filter_owner",
    "filter_from",
    "filter_to",
    "risks_table",
    "risk_form",
    "new_risk_btn",
    "editor_label",
)

_OPPS_ALIASES = (
    "opp_filter_search",
    "opp_filter_min_score",
    "opp_filter_max_score",
    "opp_filter_status",
    "opp_filter_category",
    "opp_filter_owner",
    "opp_filter_from",
    "opp_filter_to",
    "opp_filter_report",
    "opps_table",
    "opp_editor_label",
    "opp_form",
    "new_opp_btn",
)


class LayoutMixin:
    """MainWindow mixin: LayoutMixin"""

    def _build_ui(self) -> None:
        """Construct all Qt widgets and wire callbacks."""

        def bind(src: object, names: tuple[str, ...], **renamed: str) -> None:
            for name in names:
                setattr(self, name, getattr(src, name))
            for dst, src_name in renamed.items():
                setattr(self, dst, getattr(src, src_name))

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
        self.tabs.setStyleSheet("""
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
            """)

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
        bind(
            self.risks_tab,
            _RISKS_ALIASES,
            _table_card="table_card",
            _editor_card="editor_card",
        )

        # Tab: Opportunities
        self.opps_tab = OpportunitiesTab(
            on_export_csv=self._export_opportunities_csv,
            on_refresh=lambda: self._refresh_opportunities(
                select_id=self.current_opportunity_id
            ),
            on_opportunity_clicked=self._on_opportunity_clicked,
            on_new_opportunity=self._start_new_opportunity,
            on_save_opportunity=self._save_opportunity,
            on_mark_dirty=self._mark_opp_editor_dirty,
        )
        self.tabs.addTab(self.opps_tab, "Opportunities")
        bind(self.opps_tab, _OPPS_ALIASES, _opp_editor_card="editor_card")

        # Tab: Matrix
        self.matrix_tab = MatrixTab(on_kind_changed=self._on_matrix_kind_changed)
        self.tabs.addTab(self.matrix_tab, "Matrix")
        self.risks_matrix_table = self.matrix_tab.risks_matrix_table
        self.opps_matrix_table = self.matrix_tab.opps_matrix_table

        # Tab: Top history
        self.top_tab = TopHistoryTab(
            on_snapshot_now=self._snapshot_now,
            on_refresh_history=self._refresh_top_history,
            on_period_changed=self._on_top_period_changed,
            on_maybe_auto_snapshot=self._maybe_auto_snapshot,
        )
        self.tabs.addTab(self.top_tab, "Top history")

        # Ensure period selection initializes from/to range + disables edits when not Custom.
        self._on_top_period_changed(self.top_tab.top_period.currentText())

        # Tab: Actions
        self.actions_tab = ActionsTab(
            on_action_clicked=self._on_action_clicked,
            on_save_action=self._save_action,
            on_new_action=self._start_new_action,
            on_target_type_changed=lambda _text: self._toggle_action_target_inputs(),
        )
        self.tabs.addTab(self.actions_tab, "Actions")

        # Tab: Assessments
        self.assessments_tab = AssessmentsTab(on_save_assessment=self._save_assessment)
        self.tabs.addTab(self.assessments_tab, "Assessments")

        # Tab: Members
        self.members_tab = MembersTab(
            on_add_or_update_member=self._add_or_update_member,
            on_remove_selected_member=self._remove_selected_member,
            on_refresh_members=self._refresh_members,
            on_member_selected=self._on_member_selected,
        )
        self.tabs.addTab(self.members_tab, "Members")

        # Layout polish
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)

        # Keep the original spacing tweaks for the most dense tabs.
        self.risks_tab.layout().setContentsMargins(8, 8, 8, 8)
        self.risks_tab.layout().setSpacing(8)
        self.matrix_tab.layout().setContentsMargins(8, 8, 8, 8)
        self.matrix_tab.layout().setSpacing(8)

        root_layout.addLayout(left, 1)
        root_layout.addWidget(self.tabs, 3)

        root.setLayout(root_layout)
        self.setCentralWidget(root)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._load_projects()
