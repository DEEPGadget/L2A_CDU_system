"""Alarm overlay widget — floating panel shown when alarm badge is tapped.

Parented to MonitoringPage but not added to any layout.
Positioned absolutely via MonitoringPage.toggle_alarm_overlay().
Auto-hides when all alarms are cleared.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

_ALARM_LABELS: dict[str, str] = {
    "alarm:coolant_temp_warning":      "Coolant Temp — Warning",
    "alarm:coolant_temp_critical":     "Coolant Temp — Critical",
    "alarm:coolant_delta_warning":     "Coolant ΔT — Warning",
    "alarm:coolant_delta_critical":    "Coolant ΔT — Critical",
    "alarm:water_level_warning":       "Coolant Level — Warning (Middle)",
    "alarm:leak_detected":             "Leak — Detected",
    "alarm:ambient_temp_warning":      "Ambient Temp — Warning",
    "alarm:ambient_temp_critical":     "Ambient Temp — Critical",
    "alarm:ambient_humidity_warning":  "Ambient Humidity — Warning",
    "alarm:ambient_humidity_critical": "Ambient Humidity — Critical",
    "alarm:comm_timeout":              "Link — Timeout",
    "alarm:comm_disconnected":         "Link — Disconnected",
}

_CRITICAL_COLOR = QColor("#e74c3c")
_WARNING_COLOR  = QColor("#e67e22")


def _is_critical(key: str) -> bool:
    return "critical" in key or "leak" in key or "disconnected" in key


class AlarmOverlayWidget(QFrame):
    """Floating alarm list. Parented to MonitoringPage, not in any layout."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._alarms: set[str] = set()
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background:#ffffff; border:1px solid #bdc3c7; border-radius:8px; }"
        )
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Active Alarms")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:14px; color:#2c3e50; }"
            "QPushButton:hover { color:#e74c3c; }"
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Alarm list
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.setSpacing(3)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setMaximumHeight(240)
        self._list.setStyleSheet("QListWidget { border:none; }")

        item_font = QFont()
        item_font.setPointSize(12)
        self._item_font = item_font

        layout.addWidget(self._list)

    # ------------------------------------------------------------------
    # Signal handlers

    def on_alarm_set(self, key: str) -> None:
        if key in self._alarms:
            return
        self._alarms.add(key)
        label = _ALARM_LABELS.get(key, key)
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, key)
        item.setForeground(_CRITICAL_COLOR if _is_critical(key) else _WARNING_COLOR)
        item.setFont(self._item_font)
        self._list.addItem(item)

    def on_alarm_deleted(self, key: str) -> None:
        self._alarms.discard(key)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.UserRole) == key:
                self._list.takeItem(i)
                break
        if not self._alarms:
            self.hide()
