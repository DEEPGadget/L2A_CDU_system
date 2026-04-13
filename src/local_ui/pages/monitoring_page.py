"""Monitoring page.

Layout:
  QHBoxLayout
  ├── 70%  CoolingHealthWidget
  └── 30%  QVBoxLayout
            ├── ActiveAlarmsWidget
            └── ControlPanelWidget

Receives sensor / alarm signals from main window and routes them to widgets.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from src.local_ui.widgets.active_alarms import ActiveAlarmsWidget
from src.local_ui.widgets.control_panel import ControlPanelWidget
from src.local_ui.widgets.cooling_health import CoolingHealthWidget


class MonitoringPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.cooling_health = CoolingHealthWidget()
        main_layout.addWidget(self.cooling_health, stretch=7)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        self.active_alarms = ActiveAlarmsWidget()
        self.control_panel = ControlPanelWidget()

        right_panel.addWidget(self.active_alarms, stretch=1)
        right_panel.addWidget(self.control_panel, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        main_layout.addWidget(right_widget, stretch=3)

    # ------------------------------------------------------------------
    # Signal routing (called by main window)

    def on_sensor_updated(self, key: str, value: str) -> None:
        if key == "sensor:water_level_high":
            self.cooling_health.on_water_level_high(value)
        elif key == "sensor:water_level_low":
            self.cooling_health.on_water_level_low(value)
        else:
            self.cooling_health.on_sensor_updated(key, value)
        self.control_panel.on_sensor_updated(key, value)

    def on_alarm_set(self, key: str) -> None:
        self.active_alarms.on_alarm_set(key)

    def on_alarm_deleted(self, key: str) -> None:
        self.active_alarms.on_alarm_deleted(key)
