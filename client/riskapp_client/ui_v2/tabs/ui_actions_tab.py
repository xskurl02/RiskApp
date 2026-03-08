# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'actions_tab.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(403, 861)
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label = QLabel(Form)
        self.label.setObjectName(u"label")

        self.verticalLayout.addWidget(self.label)

        self.splitter = QSplitter(Form)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        self.table_card = QFrame(self.splitter)
        self.table_card.setObjectName(u"table_card")
        self.table_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.table_card.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.table_card)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.actions_table = QTableWidget(self.table_card)
        if (self.actions_table.columnCount() < 5):
            self.actions_table.setColumnCount(5)
        __qtablewidgetitem = QTableWidgetItem()
        self.actions_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.actions_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.actions_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.actions_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.actions_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        self.actions_table.setObjectName(u"actions_table")

        self.verticalLayout_2.addWidget(self.actions_table)

        self.splitter.addWidget(self.table_card)
        self.editor_card = QFrame(self.splitter)
        self.editor_card.setObjectName(u"editor_card")
        self.editor_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.editor_card.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.editor_card)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.action_editor_label = QLabel(self.editor_card)
        self.action_editor_label.setObjectName(u"action_editor_label")

        self.verticalLayout_3.addWidget(self.action_editor_label)

        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.targetTypeLabel = QLabel(self.editor_card)
        self.targetTypeLabel.setObjectName(u"targetTypeLabel")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.targetTypeLabel)

        self.action_target_type = QComboBox(self.editor_card)
        self.action_target_type.setObjectName(u"action_target_type")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.action_target_type)

        self.riskLabel = QLabel(self.editor_card)
        self.riskLabel.setObjectName(u"riskLabel")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.riskLabel)

        self.action_risk_combo = QComboBox(self.editor_card)
        self.action_risk_combo.setObjectName(u"action_risk_combo")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.action_risk_combo)

        self.opportunityLabel = QLabel(self.editor_card)
        self.opportunityLabel.setObjectName(u"opportunityLabel")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.opportunityLabel)

        self.action_opp_combo = QComboBox(self.editor_card)
        self.action_opp_combo.setObjectName(u"action_opp_combo")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.action_opp_combo)

        self.kindLabel = QLabel(self.editor_card)
        self.kindLabel.setObjectName(u"kindLabel")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.kindLabel)

        self.action_kind = QComboBox(self.editor_card)
        self.action_kind.setObjectName(u"action_kind")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.action_kind)

        self.statusLabel = QLabel(self.editor_card)
        self.statusLabel.setObjectName(u"statusLabel")

        self.formLayout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.statusLabel)

        self.action_status = QComboBox(self.editor_card)
        self.action_status.setObjectName(u"action_status")

        self.formLayout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.action_status)

        self.titleLabel = QLabel(self.editor_card)
        self.titleLabel.setObjectName(u"titleLabel")

        self.formLayout.setWidget(5, QFormLayout.ItemRole.LabelRole, self.titleLabel)

        self.action_title = QLineEdit(self.editor_card)
        self.action_title.setObjectName(u"action_title")

        self.formLayout.setWidget(5, QFormLayout.ItemRole.FieldRole, self.action_title)

        self.descriptionLabel = QLabel(self.editor_card)
        self.descriptionLabel.setObjectName(u"descriptionLabel")

        self.formLayout.setWidget(6, QFormLayout.ItemRole.LabelRole, self.descriptionLabel)

        self.action_desc = QTextEdit(self.editor_card)
        self.action_desc.setObjectName(u"action_desc")
        self.action_desc.setMaximumSize(QSize(16777215, 40))

        self.formLayout.setWidget(6, QFormLayout.ItemRole.FieldRole, self.action_desc)

        self.ownerUser_idOptionalLabel = QLabel(self.editor_card)
        self.ownerUser_idOptionalLabel.setObjectName(u"ownerUser_idOptionalLabel")

        self.formLayout.setWidget(7, QFormLayout.ItemRole.LabelRole, self.ownerUser_idOptionalLabel)

        self.action_owner = QLineEdit(self.editor_card)
        self.action_owner.setObjectName(u"action_owner")

        self.formLayout.setWidget(7, QFormLayout.ItemRole.FieldRole, self.action_owner)


        self.verticalLayout_3.addLayout(self.formLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.action_save_btn = QPushButton(self.editor_card)
        self.action_save_btn.setObjectName(u"action_save_btn")

        self.horizontalLayout_2.addWidget(self.action_save_btn)

        self.action_new_btn = QPushButton(self.editor_card)
        self.action_new_btn.setObjectName(u"action_new_btn")

        self.horizontalLayout_2.addWidget(self.action_new_btn)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout_3.addLayout(self.horizontalLayout_2)

        self.splitter.addWidget(self.editor_card)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.label.setText(QCoreApplication.translate("Form", u"Actions (mitigation/contingency/exploit)", None))
        ___qtablewidgetitem = self.actions_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("Form", u"Title", None));
        ___qtablewidgetitem1 = self.actions_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("Form", u"Kind", None));
        ___qtablewidgetitem2 = self.actions_table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("Form", u"Status", None));
        ___qtablewidgetitem3 = self.actions_table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("Form", u"Target", None));
        ___qtablewidgetitem4 = self.actions_table.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("Form", u"Owner", None));
        self.action_editor_label.setText(QCoreApplication.translate("Form", u"Editor (new action)", None))
        self.targetTypeLabel.setText(QCoreApplication.translate("Form", u"Target type", None))
        self.riskLabel.setText(QCoreApplication.translate("Form", u"Risk", None))
        self.opportunityLabel.setText(QCoreApplication.translate("Form", u"Opportunity", None))
        self.kindLabel.setText(QCoreApplication.translate("Form", u"Kind", None))
        self.statusLabel.setText(QCoreApplication.translate("Form", u"Status", None))
        self.titleLabel.setText(QCoreApplication.translate("Form", u"Title", None))
        self.descriptionLabel.setText(QCoreApplication.translate("Form", u"Description", None))
        self.ownerUser_idOptionalLabel.setText(QCoreApplication.translate("Form", u"Owner user_id (optional)", None))
        self.action_save_btn.setText(QCoreApplication.translate("Form", u"Save", None))
        self.action_new_btn.setText(QCoreApplication.translate("Form", u"New action", None))
    # retranslateUi

