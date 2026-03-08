# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'members_tab.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(451, 187)
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.members_hint = QLabel(Form)
        self.members_hint.setObjectName(u"members_hint")

        self.verticalLayout.addWidget(self.members_hint)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label = QLabel(Form)
        self.label.setObjectName(u"label")

        self.horizontalLayout.addWidget(self.label)

        self.member_email = QLineEdit(Form)
        self.member_email.setObjectName(u"member_email")

        self.horizontalLayout.addWidget(self.member_email)

        self.label_2 = QLabel(Form)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout.addWidget(self.label_2)

        self.member_role = QComboBox(Form)
        self.member_role.addItem("")
        self.member_role.addItem("")
        self.member_role.addItem("")
        self.member_role.addItem("")
        self.member_role.setObjectName(u"member_role")
        self.member_role.setEditable(True)

        self.horizontalLayout.addWidget(self.member_role)

        self.member_add_btn = QPushButton(Form)
        self.member_add_btn.setObjectName(u"member_add_btn")

        self.horizontalLayout.addWidget(self.member_add_btn)

        self.member_remove_btn = QPushButton(Form)
        self.member_remove_btn.setObjectName(u"member_remove_btn")

        self.horizontalLayout.addWidget(self.member_remove_btn)

        self.member_refresh_btn = QPushButton(Form)
        self.member_refresh_btn.setObjectName(u"member_refresh_btn")

        self.horizontalLayout.addWidget(self.member_refresh_btn)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.members_table = QTableWidget(Form)
        if (self.members_table.columnCount() < 4):
            self.members_table.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.members_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.members_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.members_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.members_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.members_table.setObjectName(u"members_table")
        self.members_table.horizontalHeader().setCascadingSectionResizes(True)

        self.verticalLayout.addWidget(self.members_table)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.members_hint.setText(QCoreApplication.translate("Form", u"Project members and roles (admin only for changes).", None))
        self.label.setText(QCoreApplication.translate("Form", u"Email", None))
        self.member_email.setPlaceholderText(QCoreApplication.translate("Form", u"user@example.com", None))
        self.label_2.setText(QCoreApplication.translate("Form", u"Role", None))
        self.member_role.setItemText(0, QCoreApplication.translate("Form", u"viewer", None))
        self.member_role.setItemText(1, QCoreApplication.translate("Form", u"member", None))
        self.member_role.setItemText(2, QCoreApplication.translate("Form", u"manager", None))
        self.member_role.setItemText(3, QCoreApplication.translate("Form", u"admin", None))

        self.member_add_btn.setText(QCoreApplication.translate("Form", u"Add/Update", None))
        self.member_remove_btn.setText(QCoreApplication.translate("Form", u"Remove selected", None))
        self.member_refresh_btn.setText(QCoreApplication.translate("Form", u"Refresh", None))
        ___qtablewidgetitem = self.members_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("Form", u"Email", None));
        ___qtablewidgetitem1 = self.members_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("Form", u"Role", None));
        ___qtablewidgetitem2 = self.members_table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("Form", u"User ID", None));
        ___qtablewidgetitem3 = self.members_table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("Form", u"Added at", None));
    # retranslateUi

