from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt  # pylint: disable=no-name-in-module
from PySide6.QtGui import QColor, QPen  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)  # pylint: disable=no-name-in-module


# -------------------------
# Minimal login dialog (only shown if env vars are missing)
# -------------------------
class LoginDialog(QDialog):
    def __init__(
        self, *, default_url: str = "http://localhost:8000", parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect to server")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.url = QLineEdit(default_url)
        self.email = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form.addRow("Server URL", self.url)
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.url.text().strip(),
            self.email.text().strip(),
            self.password.text(),
        )


# -------------------------
# UI
# -------------------------
class ExcelSelectionDelegate(QStyledItemDelegate):
    """Grey selection for whole selected row, and a single 'active cell' border.
    Also renders a 'row number gutter' inside the Title column.
    """

    GUTTER_W = 24
    # Title is column 1 in the scored-entity tables (Code, Title, ...)
    GUTTER_COL = 1

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        if index.column() == self.GUTTER_COL:
            return QSize(s.width() + self.GUTTER_W + 10, s.height())
        return s

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)

        # background
        if opt.state & QStyle.State_Selected:
            bg = QColor(230, 230, 230)
        elif opt.state & QStyle.State_MouseOver:
            bg = QColor(245, 245, 245)
        else:
            bg = QColor("white")

        painter.save()
        painter.fillRect(opt.rect, bg)
        painter.restore()

        if index.column() == self.GUTTER_COL:
            rect = opt.rect
            gutter = QRect(rect.left(), rect.top(), self.GUTTER_W, rect.height())

            # separator line between number and title
            painter.save()
            pen = QPen(QColor(208, 208, 208), 1)
            pen.setCosmetic(True)
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)

            x = rect.left() + self.GUTTER_W
            painter.drawLine(x, rect.top(), x, rect.bottom() - 1)
            painter.restore()

            # number (row index)
            num = str(index.row() + 1)
            painter.save()
            painter.setPen(opt.palette.text().color())
            painter.drawText(gutter.adjusted(0, 0, -1, 0), Qt.AlignCenter, num)
            painter.restore()

            # title text
            title = index.data() or ""
            pad = 8
            title_rect = rect.adjusted(self.GUTTER_W + pad, 0, -pad, 0)

            painter.save()
            painter.setPen(opt.palette.text().color())
            fm = opt.fontMetrics
            full_w = fm.horizontalAdvance(title)
            elided = fm.elidedText(title, Qt.ElideRight, max(0, title_rect.width()))
            align = Qt.AlignVCenter | (
                Qt.AlignHCenter if full_w <= title_rect.width() else Qt.AlignLeft
            )
            painter.drawText(title_rect, align, elided)
            painter.restore()
        else:
            # default painting for other columns (but no blue selection)
            opt.state &= ~QStyle.State_Selected
            opt.state &= ~QStyle.State_MouseOver
            super().paint(painter, opt, index)

        # active cell border
        if opt.state & QStyle.State_HasFocus:
            painter.save()
            pen = QPen(opt.palette.highlight().color(), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(opt.rect.adjusted(1, 1, -1, -1))
            painter.restore()

        # excel-like internal gridlines
        painter.save()
        pen = QPen(QColor(208, 208, 208), 1)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)

        r = opt.rect
        model = index.model()
        last_col = model.columnCount(index.parent()) - 1
        last_row = model.rowCount(index.parent()) - 1

        if index.column() < last_col:
            x = r.right()
            y2 = r.bottom() if index.row() == last_row else (r.bottom() - 1)
            painter.drawLine(x, r.top(), x, y2)

        if index.row() < last_row:
            y = r.bottom()
            x2 = r.right() if index.column() == last_col else (r.right() - 1)
            painter.drawLine(r.left(), y, x2, y)

        painter.restore()


def setup_readonly_table(table: QTableWidget, *, excel_delegate: bool = False) -> None:
    """Apply standard readonly 'list table' behavior used across tabs.

    Call-sites import this from ``riskapp_client.ui.components.custom_gui_widgets``.
    """
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setFocusPolicy(Qt.StrongFocus)
    if excel_delegate:
        table.setItemDelegate(ExcelSelectionDelegate(table))


class RiskForm(QWidget):
    """
    Editor used for creating/updating a risk OR opportunity (same shape).
    Calls on_submit(payload_dict).
    """

    STATUS_CHOICES = ["concept", "active", "closed", "deleted", "happened"]

    def __init__(self, on_submit) -> None:
        super().__init__()
        self.on_submit = on_submit
        self._allow_deleted_status: bool = True

        layout = QFormLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(10)

        # --- Core fields ---
        self.code = QLineEdit()
        self.code.setPlaceholderText(
            "Optional (e.g. R-001 / O-001). Leave empty to auto-generate on server."
        )
        self.code.setToolTip(
            "Označení (unique code). Used for searching/filtering in the register.\n"
            "Tip: keep it short and stable (e.g. R-001)."
        )

        self.title = QLineEdit()
        self.title.setToolTip("Název. Short, descriptive name of the risk/opportunity.")

        self.category = QLineEdit()
        self.category.setPlaceholderText("e.g. cost / time / scope / quality")
        self.category.setToolTip(
            "Kategorie. Helps grouping and reporting (e.g. cost, time, scope, quality)."
        )

        self.status = QComboBox()
        self.status.setEditable(True)
        self.status.addItems(self.STATUS_CHOICES)
        self.status.setToolTip(
            "Stav. Lifecycle state (concept/active/closed/deleted/happened).\n"
            "Changing status updates 'status_changed_at' on the server."
        )

        # Owner / responsible person
        # Use an editable combo populated from project members (still allows pasting a UUID manually).
        self.owner_user_id = QComboBox()
        self.owner_user_id.setEditable(True)
        self.owner_user_id.addItem("(none)", None)
        if self.owner_user_id.lineEdit():
            self.owner_user_id.lineEdit().setPlaceholderText(
                "Select member or paste UUID (optional)"
            )
        self.owner_user_id.setToolTip(
            "Vlastník. Responsible person for monitoring/handling this item."
        )

        # --- Qualitative ---
        self.p = QSpinBox()
        self.p.setRange(1, 5)
        self.p.setValue(3)
        self.p.setToolTip(
            "Pravděpodobnost (1-5). Qualitative likelihood of the event/opportunity."
        )

        # impact dimensions
        self.impact_cost = QSpinBox()
        self.impact_cost.setRange(1, 5)
        self.impact_cost.setValue(3)
        self.impact_cost.setToolTip("Dopad - Náklady (1-5).")
        self.impact_time = QSpinBox()
        self.impact_time.setRange(1, 5)
        self.impact_time.setValue(3)
        self.impact_time.setToolTip("Dopad - Čas (1-5).")
        self.impact_scope = QSpinBox()
        self.impact_scope.setRange(1, 5)
        self.impact_scope.setValue(3)
        self.impact_scope.setToolTip("Dopad - Rozsah (1-5).")
        self.impact_quality = QSpinBox()
        self.impact_quality.setRange(1, 5)
        self.impact_quality.setValue(3)
        self.impact_quality.setToolTip("Dopad - Kvalita (1-5).")

        # overall impact (read-only, derived)
        self.i = QSpinBox()
        self.i.setRange(1, 5)
        self.i.setValue(3)
        self.i.setEnabled(False)
        self.i.setToolTip(
            "Celkový dopad (1-5). Derived as MAX(cost,time,scope,quality)."
        )

        for w in (
            self.impact_cost,
            self.impact_time,
            self.impact_scope,
            self.impact_quality,
        ):
            w.valueChanged.connect(self._recompute_overall_impact)

        # --- Rich text fields ---
        self.description = QTextEdit()
        self.description.setPlaceholderText("Detailed description / link to doc…")
        self.description.setToolTip(
            "Popis. More detailed description, assumptions, context and references."
        )

        self.threat = QTextEdit()
        self.threat.setPlaceholderText("Root cause…")
        self.threat.setToolTip(
            "Hrozba. Root cause / primary driver behind the risk/opportunity."
        )

        self.triggers = QTextEdit()
        self.triggers.setPlaceholderText("Indicators / triggers…")
        self.triggers.setToolTip(
            "Spouštěče. Observable indicators that the event is happening/likely."
        )

        self.mitigation_plan = QTextEdit()
        self.mitigation_plan.setPlaceholderText("Response / mitigation plan…")
        self.mitigation_plan.setToolTip(
            "Reakce/Opatření. Planned response (mitigation/contingency/exploit)."
        )

        self.document_url = QLineEdit()
        self.document_url.setPlaceholderText("Optional link to document (URL)")
        self.document_url.setToolTip(
            "Odkaz na dokument. Optional URL to supporting documentation."
        )

        # --- Dates (ISO strings; empty allowed) ---
        self.identified_at = QLineEdit()
        self.identified_at.setPlaceholderText(
            "ISO datetime or date (e.g. 2026-02-19 or 2026-02-19T10:00:00)"
        )
        self.identified_at.setToolTip(
            "Datum identifikace. Leave empty to use 'now'. Accepts ISO date or datetime."
        )

        self.response_at = QLineEdit()
        self.response_at.setPlaceholderText("ISO datetime/date (optional)")
        self.response_at.setToolTip(
            "Datum reakce. When the mitigation/response was applied (optional)."
        )

        self.occurred_at = QLineEdit()
        self.occurred_at.setPlaceholderText("ISO datetime/date (optional)")
        self.occurred_at.setToolTip(
            "Datum události. When the risk event happened (optional)."
        )

        # status_changed_at is usually server-managed; keep hidden but present
        self.status_changed_at = QLineEdit()
        self.status_changed_at.setPlaceholderText(
            "ISO datetime (auto when status changes)"
        )
        self.status_changed_at.setVisible(False)

        layout.addRow("Code", self.code)
        layout.addRow("Title", self.title)
        layout.addRow("Category", self.category)
        layout.addRow("Status", self.status)
        layout.addRow("Owner user_id", self.owner_user_id)
        layout.addRow("Probability (1-5)", self.p)
        layout.addRow("Impact - Cost (1-5)", self.impact_cost)
        layout.addRow("Impact - Time (1-5)", self.impact_time)
        layout.addRow("Impact - Scope (1-5)", self.impact_scope)
        layout.addRow("Impact - Quality (1-5)", self.impact_quality)
        layout.addRow("Impact (overall, max)", self.i)
        layout.addRow("Description", self.description)
        layout.addRow("Threat", self.threat)
        layout.addRow("Triggers", self.triggers)
        layout.addRow("Mitigation/Response", self.mitigation_plan)
        layout.addRow("Document URL", self.document_url)
        layout.addRow("Identified at", self.identified_at)
        layout.addRow("Response at", self.response_at)
        layout.addRow("Occurred at", self.occurred_at)

        self.btn = QPushButton("Save")
        self.btn.clicked.connect(self._submit)
        self.btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(self.btn)

        self.setLayout(layout)

    def set_allow_deleted_status(self, allowed: bool) -> None:
        """Enable/disable the 'deleted' lifecycle state in the dropdown.

        Server-side authorization is the real gate; this is UX-level protection
        to reduce accidental "soft delete" attempts by non-managers.
        """

        allowed = bool(allowed)
        if getattr(self, "_allow_deleted_status", True) == allowed:
            return
        self._allow_deleted_status = allowed

        current = (self.status.currentText() or "").strip()
        base = ["concept", "active", "closed", "happened"]
        choices = base + (["deleted"] if allowed else [])

        self.status.blockSignals(True)
        self.status.clear()
        self.status.addItems(choices)
        # Keep it editable for power users, but remove the easy footgun.
        self.status.setEditable(True)

        if current:
            idx = self.status.findText(current)
            if idx >= 0:
                self.status.setCurrentIndex(idx)
            else:
                self.status.setEditText(current)

        self.status.blockSignals(False)

    def set_editable(self, editable: bool) -> None:
        """Enable/disable editing while keeping fields readable.

        - When editable=False, text fields become read-only and selectors/spinboxes are disabled.
        - Save button is disabled.
        """
        # Save
        self.btn.setEnabled(bool(editable))

        # Line edits
        for w in (
            self.code,
            self.title,
            self.category,
            self.document_url,
            self.identified_at,
            self.response_at,
            self.occurred_at,
            self.status_changed_at,
        ):
            w.setReadOnly(not editable)

        # Rich text
        for w in (self.description, self.threat, self.triggers, self.mitigation_plan):
            w.setReadOnly(not editable)

        # Combos
        self.status.setEnabled(bool(editable))
        self.owner_user_id.setEnabled(bool(editable))

        # Spinboxes (impact is derived/read-only already)
        self.p.setEnabled(bool(editable))
        for w in (
            self.impact_cost,
            self.impact_time,
            self.impact_scope,
            self.impact_quality,
        ):
            w.setEnabled(bool(editable))
        self.i.setEnabled(False)

    def set_members(self, members) -> None:
        """Populate owner dropdown from project members."""
        current = self._owner_value()
        self.owner_user_id.blockSignals(True)
        self.owner_user_id.clear()
        self.owner_user_id.addItem("(none)", None)
        for m in members or []:
            try:
                uid = getattr(m, "user_id", None) or (
                    m.get("user_id") if isinstance(m, dict) else None
                )
                email = getattr(m, "email", None) or (
                    m.get("email") if isinstance(m, dict) else None
                )
                role = getattr(m, "role", None) or (
                    m.get("role") if isinstance(m, dict) else None
                )
            except Exception:
                continue
            if not uid:
                continue
            label = f"{email or uid} ({role or 'member'})"
            self.owner_user_id.addItem(label, str(uid))

        self._set_owner_value(current)
        self.owner_user_id.blockSignals(False)

    def _find_owner_index(self, user_id: str) -> int:
        for i in range(self.owner_user_id.count()):
            if str(self.owner_user_id.itemData(i) or "") == str(user_id):
                return i
        return -1

    def _set_owner_value(self, user_id: str | None) -> None:
        if not user_id:
            self.owner_user_id.setCurrentIndex(0)
            self.owner_user_id.setEditText("")
            return
        idx = self._find_owner_index(str(user_id))
        if idx >= 0:
            self.owner_user_id.setCurrentIndex(idx)
        else:
            self.owner_user_id.setEditText(str(user_id))

    def _owner_value(self) -> str | None:
        data = self.owner_user_id.currentData()
        if data:
            return str(data)
        txt = (self.owner_user_id.currentText() or "").strip()
        if not txt or txt == "(none)":
            return None
        return txt

    def _recompute_overall_impact(self) -> None:
        overall = max(
            int(self.impact_cost.value()),
            int(self.impact_time.value()),
            int(self.impact_scope.value()),
            int(self.impact_quality.value()),
        )
        self.i.setValue(overall)

    def get_payload(self) -> dict:
        # no validation here (caller decides)
        self._recompute_overall_impact()
        return {
            "code": (self.code.text().strip() or None),
            "title": (self.title.text().strip() or ""),
            "category": (self.category.text().strip() or None),
            "status": (self.status.currentText().strip() or None),
            "owner_user_id": self._owner_value(),
            "probability": int(self.p.value()),
            "impact": int(self.i.value()),
            "impact_cost": int(self.impact_cost.value()),
            "impact_time": int(self.impact_time.value()),
            "impact_scope": int(self.impact_scope.value()),
            "impact_quality": int(self.impact_quality.value()),
            "description": (self.description.toPlainText().strip() or None),
            "threat": (self.threat.toPlainText().strip() or None),
            "triggers": (self.triggers.toPlainText().strip() or None),
            "mitigation_plan": (self.mitigation_plan.toPlainText().strip() or None),
            "document_url": (self.document_url.text().strip() or None),
            "identified_at": (self.identified_at.text().strip() or None),
            "status_changed_at": (self.status_changed_at.text().strip() or None),
            "response_at": (self.response_at.text().strip() or None),
            "occurred_at": (self.occurred_at.text().strip() or None),
        }

    def set_values(
        self,
        *,
        title: str = "",
        probability: int = 3,
        impact: int = 3,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = "concept",
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
    ) -> None:
        # Block signals during programmatic set
        widgets = [
            self.code,
            self.title,
            self.category,
            self.description,
            self.threat,
            self.triggers,
            self.identified_at,
            self.response_at,
            self.occurred_at,
        ]
        for w in widgets:
            w.blockSignals(True)
        self.owner_user_id.blockSignals(True)
        self.p.blockSignals(True)
        self.i.blockSignals(True)
        self.status.blockSignals(True)

        self.code.setText(code or "")
        self.title.setText(title or "")
        self.category.setText(category or "")
        self._set_owner_value(owner_user_id)

        # status combo
        st = (status or "concept").strip() or "concept"
        idx = self.status.findText(st)
        if idx >= 0:
            self.status.setCurrentIndex(idx)
        else:
            self.status.setEditText(st)

        self.p.setValue(int(probability))
        self.impact_cost.setValue(
            int(impact_cost) if impact_cost is not None else int(impact)
        )
        self.impact_time.setValue(
            int(impact_time) if impact_time is not None else int(impact)
        )
        self.impact_scope.setValue(
            int(impact_scope) if impact_scope is not None else int(impact)
        )
        self.impact_quality.setValue(
            int(impact_quality) if impact_quality is not None else int(impact)
        )
        self._recompute_overall_impact()

        self.description.setPlainText(description or "")
        self.threat.setPlainText(threat or "")
        self.triggers.setPlainText(triggers or "")
        self.mitigation_plan.setPlainText(mitigation_plan or "")
        self.document_url.setText(document_url or "")

        self.identified_at.setText(identified_at or "")
        self.status_changed_at.setText(status_changed_at or "")
        self.response_at.setText(response_at or "")
        self.occurred_at.setText(occurred_at or "")

        for w in widgets:
            w.blockSignals(False)
        self.owner_user_id.blockSignals(False)
        self.p.blockSignals(False)
        self.i.blockSignals(False)
        self.status.blockSignals(False)

    def _submit(self) -> None:
        payload = self.get_payload()
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return
        self.on_submit(payload)


class CrispHeader(QHeaderView):
    def __init__(self, orientation, parent=None, line_color: str = "#d0d0d0") -> None:
        super().__init__(orientation, parent)
        self._pen = QPen(QColor(line_color), 1)
        self._pen.setCosmetic(True)

    def paintSection(self, painter, rect, logicalIndex) -> None:
        super().paintSection(painter, rect, logicalIndex)
        painter.save()
        painter.setPen(self._pen)
        if logicalIndex < self.count() - 1:
            x = rect.right()
            painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()
