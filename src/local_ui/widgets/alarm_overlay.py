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
    # Coolant temperature — Loop 1
    "alarm:coolant_temp_l1_warning":   "Coolant Temp L1 — Warning",
    "alarm:coolant_temp_l1_critical":  "Coolant Temp L1 — Critical",
    # Coolant temperature — Loop 2
    "alarm:coolant_temp_l2_warning":   "Coolant Temp L2 — Warning",
    "alarm:coolant_temp_l2_critical":  "Coolant Temp L2 — Critical",
    # Water level
    "alarm:water_level_warning":       "Coolant Level — Warning",
    "alarm:water_level_critical":      "Coolant Level — Critical",
    # Leak
    "alarm:leak_detected":             "Leak — Detected",
    # Flow & pressure
    "alarm:flow_rate_warning":         "Flow Rate — Warning",
    "alarm:pressure_warning":          "Pressure — Warning",
    # Chemistry
    "alarm:ph_warning":                "pH — Warning",
    "alarm:conductivity_warning":      "Conductivity — Warning",
    # Ambient
    "alarm:ambient_temp_warning":      "Ambient Temp — Warning",
    "alarm:ambient_temp_critical":     "Ambient Temp — Critical",
    "alarm:ambient_humidity_warning":  "Ambient Humidity — Warning",
    "alarm:ambient_humidity_critical": "Ambient Humidity — Critical",
    # Communication
    "alarm:comm_timeout":              "Link — Timeout",
    "alarm:comm_disconnected":         "Link — Disconnected",
}

_CRITICAL_COLOR = QColor("#e74c3c")
_WARNING_COLOR  = QColor("#e67e22")


def _is_critical(key: str) -> bool:
    return "critical" in key or key == "alarm:leak_detected" or "disconnected" in key


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
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(10)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Active Alarms")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:20px; color:#2c3e50; }"
            "QPushButton:hover { color:#e74c3c; }"
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Alarm list
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.setSpacing(5)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setMaximumHeight(500)
        self._list.setStyleSheet(
            "QListWidget { border:none; }"
            "QScrollBar:vertical { width:18px; background:#f0f0f0; border-radius:9px; }"
            "QScrollBar::handle:vertical { background:#bdc3c7; border-radius:9px; min-height:40px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }"
        )

        item_font = QFont()
        item_font.setPointSize(15)
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
