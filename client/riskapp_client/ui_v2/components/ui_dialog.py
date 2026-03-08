# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFormLayout, QLabel, QLineEdit, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(400, 300)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.serverURLLabel = QLabel(Dialog)
        self.serverURLLabel.setObjectName(u"serverURLLabel")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.serverURLLabel)

        self.url = QLineEdit(Dialog)
        self.url.setObjectName(u"url")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.url)

        self.emailLabel = QLabel(Dialog)
        self.emailLabel.setObjectName(u"emailLabel")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.emailLabel)

        self.email = QLineEdit(Dialog)
        self.email.setObjectName(u"email")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.email)

        self.passwordLabel = QLabel(Dialog)
        self.passwordLabel.setObjectName(u"passwordLabel")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.passwordLabel)

        self.password = QLineEdit(Dialog)
        self.password.setObjectName(u"password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.password)


        self.verticalLayout.addLayout(self.formLayout)

        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.serverURLLabel.setText(QCoreApplication.translate("Dialog", u"Server URL", None))
        self.url.setText(QCoreApplication.translate("Dialog", u"http://localhost:8000", None))
        self.emailLabel.setText(QCoreApplication.translate("Dialog", u"Email", None))
        self.passwordLabel.setText(QCoreApplication.translate("Dialog", u"Password", None))
    # retranslateUi

