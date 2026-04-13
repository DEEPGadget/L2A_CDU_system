"""Active alarms widget.

Displays the list of currently active alarm keys.
Updates in real-time via alarm_set / alarm_deleted signals from RedisSubscriber.

When no alarms are active, shows "No active alarms".
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Human-readable labels for alarm keys
_ALARM_LABELS: dict[str, str] = {
    "alarm:coolant_temp_warning":       "Coolant Temp — Warning",
    "alarm:coolant_temp_critical":      "Coolant Temp — Critical",
    "alarm:coolant_delta_warning":      "Coolant ΔT — Warning",
    "alarm:coolant_delta_critical":     "Coolant ΔT — Critical",
    "alarm:water_level_warning":        "Coolant Level — Warning (Middle)",
    "alarm:leak_detected":              "Leak — Detected",
    "alarm:ambient_temp_warning":       "Ambient Temp — Warning",
    "alarm:ambient_temp_critical":      "Ambient Temp — Critical",
    "alarm:ambient_humidity_warning":   "Ambient Humidity — Warning",
    "alarm:ambient_humidity_critical":  "Ambient Humidity — Critical",
    "alarm:comm_timeout":               "Link — Timeout",
    "alarm:comm_disconnected":          "Link — Disconnected",
}

_CRITICAL_COLOR = QColor("#e74c3c")
_WARNING_COLOR  = QColor("#f39c12")


def _is_critical(key: str) -> bool:
    return "critical" in key or "leak" in key or "disconnected" in key


class ActiveAlarmsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._alarms: set[str] = set()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Active Alarms")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Stack: list view or empty message
        self._stack = QStackedWidget()

        self._list_widget = QListWidget()
        self._list_widget.setFocusPolicy(Qt.NoFocus)
        self._list_widget.setSpacing(2)

        self._empty_label = QLabel("No active alarms")
        self._empty_label.setAlignment(Qt.AlignCenter)
        empty_font = QFont()
        empty_font.setPointSize(12)
        empty_font.setItalic(True)
        self._empty_label.setFont(empty_font)
        self._empty_label.setStyleSheet("color: #7f8c8d;")

        self._stack.addWidget(self._list_widget)   # index 0
        self._stack.addWidget(self._empty_label)   # index 1

        self._stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._stack)

        self._show_empty()

    # ------------------------------------------------------------------
    # Signal handlers (connect from main window)

    def on_alarm_set(self, key: str) -> None:
        if key in self._alarms:
            return
        self._alarms.add(key)
        self._add_item(key)
        self._show_list()

    def on_alarm_deleted(self, key: str) -> None:
        self._alarms.discard(key)
        self._remove_item(key)
        if not self._alarms:
            self._show_empty()

    # ------------------------------------------------------------------
    # List management

    def _add_item(self, key: str) -> None:
        label = _ALARM_LABELS.get(key, key)
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, key)
        color = _CRITICAL_COLOR if _is_critical(key) else _WARNING_COLOR
        item.setForeground(color)
        font = QFont()
        font.setPointSize(12)
        item.setFont(font)
        self._list_widget.addItem(item)

    def _remove_item(self, key: str) -> None:
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item and item.data(Qt.UserRole) == key:
                self._list_widget.takeItem(i)
                return

    # ------------------------------------------------------------------
    # View switching

    def _show_list(self) -> None:
        self._stack.setCurrentIndex(0)

    def _show_empty(self) -> None:
        self._list_widget.clear()
        self._stack.setCurrentIndex(1)
