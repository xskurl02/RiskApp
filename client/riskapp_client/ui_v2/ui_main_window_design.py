# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window_design.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMenuBar,
    QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 840)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.sidebar_container = QWidget(self.splitter)
        self.sidebar_container.setObjectName(u"sidebar_container")
        self.verticalLayout = QVBoxLayout(self.sidebar_container)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.project_list_label = QLabel(self.sidebar_container)
        self.project_list_label.setObjectName(u"project_list_label")

        self.verticalLayout.addWidget(self.project_list_label)

        self.project_list = QListWidget(self.sidebar_container)
        self.project_list.setObjectName(u"project_list")

        self.verticalLayout.addWidget(self.project_list)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(-1, 0, -1, -1)
        self.sync_btn = QPushButton(self.sidebar_container)
        self.sync_btn.setObjectName(u"sync_btn")

        self.horizontalLayout_4.addWidget(self.sync_btn)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.sidebar_list = QListWidget(self.sidebar_container)
        self.sidebar_list.setObjectName(u"sidebar_list")

        self.verticalLayout.addWidget(self.sidebar_list)

        self.theme_toggle = QCheckBox(self.sidebar_container)
        self.theme_toggle.setObjectName(u"theme_toggle")

        self.verticalLayout.addWidget(self.theme_toggle)

        self.splitter.addWidget(self.sidebar_container)
        self.main_stacked_widget = QStackedWidget(self.splitter)
        self.main_stacked_widget.setObjectName(u"main_stacked_widget")
        self.page = QWidget()
        self.page.setObjectName(u"page")
        self.main_stacked_widget.addWidget(self.page)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.main_stacked_widget.addWidget(self.page_2)
        self.splitter.addWidget(self.main_stacked_widget)

        self.horizontalLayout.addWidget(self.splitter)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 18))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.main_stacked_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.project_list_label.setText(QCoreApplication.translate("MainWindow", u"Projects", None))
        self.sync_btn.setText(QCoreApplication.translate("MainWindow", u"Sync Now", None))
        self.theme_toggle.setText(QCoreApplication.translate("MainWindow", u"Dark Mode", None))
    # retranslateUi

