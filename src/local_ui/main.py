import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt
from pages.monitoring_page import MonitoringPage
from pages.history_page import HistoryPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("L2A CDU")
        self.showFullScreen()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav = QHBoxLayout()
        nav.setContentsMargins(8, 8, 8, 8)
        btn_monitoring = QPushButton("Monitoring")
        btn_history = QPushButton("History")
        btn_monitoring.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_history.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        nav.addWidget(btn_monitoring)
        nav.addWidget(btn_history)
        nav.addStretch()

        self.stack = QStackedWidget()
        self.stack.addWidget(MonitoringPage())
        self.stack.addWidget(HistoryPage())

        layout.addLayout(nav)
        layout.addWidget(self.stack)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
