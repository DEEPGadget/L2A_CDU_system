"""Local UI entry point.

Startup sequence:
  1. Load config/config.yaml → confirm mode
  2. Enable Redis keyspace notifications (required for alarm:* events)
  3. Start RedisSubscriber thread
  4. Build MainWindow (TopBar + QStackedWidget[Monitoring, History])
  5. Wire signals from RedisSubscriber → widgets
  6. Show window (fullscreen on RPi, normal window on desktop)
  7. On exit: stop subscriber thread

Run:
    python src/local_ui/main.py
"""

from __future__ import annotations

import logging
import os
import sys

import redis
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config import get_config
from src.local_ui.pages.history_page import HistoryPage
from src.local_ui.pages.monitoring_page import MonitoringPage
from src.local_ui.redis_subscriber import RedisSubscriber
from src.local_ui.widgets.top_bar import TopBarWidget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [local_ui] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

_IS_RPI = os.path.exists("/sys/firmware/devicetree/base/model")


def _enable_keyspace_notifications(r: redis.Redis) -> None:
    """Enable Redis keyspace events so alarm:* SET/DEL can be subscribed."""
    try:
        r.config_set("notify-keyspace-events", "KEA")
        log.info("Redis keyspace notifications enabled.")
    except Exception as e:
        log.warning("Could not enable keyspace notifications: %s", e)


class MainWindow(QMainWindow):
    def __init__(self, subscriber: RedisSubscriber) -> None:
        super().__init__()
        self.setWindowTitle("L2A CDU System")
        self._subscriber = subscriber
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._monitoring_page = MonitoringPage()
        self._history_page    = HistoryPage()
        self._stack.addWidget(self._monitoring_page)   # index 0
        self._stack.addWidget(self._history_page)      # index 1

        self._top_bar = TopBarWidget(self._stack)
        self._top_bar.setFixedHeight(52)

        layout.addWidget(self._top_bar)
        layout.addWidget(self._stack)

    def _connect_signals(self) -> None:
        sub = self._subscriber

        # Sensor updates → monitoring page + top bar
        sub.sensor_updated.connect(self._monitoring_page.on_sensor_updated)

        # Comm updates → top bar
        sub.comm_updated.connect(self._top_bar.on_comm_updated)

        # Alarm signals → top bar + monitoring page
        sub.alarm_set.connect(self._top_bar.on_alarm_set)
        sub.alarm_set.connect(self._monitoring_page.on_alarm_set)
        sub.alarm_deleted.connect(self._top_bar.on_alarm_deleted)
        sub.alarm_deleted.connect(self._monitoring_page.on_alarm_deleted)

    def closeEvent(self, event) -> None:
        self._subscriber.stop()
        super().closeEvent(event)


def main() -> None:
    cfg = get_config()
    log.info("Starting local UI — mode=%s", cfg.mode)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    _enable_keyspace_notifications(r)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    subscriber = RedisSubscriber()
    subscriber.start()

    window = MainWindow(subscriber)

    if _IS_RPI:
        from PySide6.QtCore import Qt
        screen_geo = app.primaryScreen().geometry()
        window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        window.setGeometry(screen_geo)
        window.show()
    else:
        window.resize(1280, 720)
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
