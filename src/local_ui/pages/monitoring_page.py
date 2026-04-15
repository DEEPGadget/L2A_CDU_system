"""Monitoring page.

Layout (top → bottom):
  QVBoxLayout
  ├── CoolingHealthWidget   (stretch=1, full-width SVG diagram)
  └── StatusStripWidget     (fixed 76px, ΔT / Leak / Ambient / Pressure)

AlarmOverlayWidget is a floating child (not in layout).
Toggled by TopBarWidget.bell_tapped signal via toggle_alarm_overlay().
Tap-outside dismissal via eventFilter.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.local_ui.widgets.alarm_overlay import AlarmOverlayWidget
from src.local_ui.widgets.cooling_health import CoolingHealthWidget
from src.local_ui.widgets.status_strip import StatusStripWidget


class MonitoringPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._alarm_overlay: AlarmOverlayWidget | None = None
        self._build_ui()
        self.installEventFilter(self)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.cooling_health = CoolingHealthWidget()
        layout.addWidget(self.cooling_health, stretch=1)

        self.status_strip = StatusStripWidget()
        layout.addWidget(self.status_strip)

        # Floating overlay — parented to this widget, not in any layout
        self._alarm_overlay = AlarmOverlayWidget(self)

    # ------------------------------------------------------------------
    # Alarm overlay control

    def toggle_alarm_overlay(self) -> None:
        if self._alarm_overlay.isVisible():
            self._alarm_overlay.hide()
        else:
            self._reposition_overlay()
            self._alarm_overlay.show()
            self._alarm_overlay.raise_()

    def _reposition_overlay(self) -> None:
        overlay = self._alarm_overlay
        overlay.adjustSize()
        ow = overlay.width() or 320
        oh = overlay.height()
        x = self.width() - ow - 8
        y = 8
        overlay.setGeometry(x, y, ow, oh)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._alarm_overlay and self._alarm_overlay.isVisible():
            self._reposition_overlay()

    def eventFilter(self, obj, event) -> bool:
        if (
            obj is self
            and event.type() == QEvent.MouseButtonPress
            and self._alarm_overlay
            and self._alarm_overlay.isVisible()
        ):
            if not self._alarm_overlay.geometry().contains(event.pos()):
                self._alarm_overlay.hide()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Signal routing (called by main window)

    def on_sensor_updated(self, key: str, value: str) -> None:
        if key == "sensor:water_level_high":
            self.cooling_health.on_water_level_high(value)
        elif key == "sensor:water_level_low":
            self.cooling_health.on_water_level_low(value)
        else:
            self.cooling_health.on_sensor_updated(key, value)
        self.status_strip.on_sensor_updated(key, value)

    def on_alarm_set(self, key: str) -> None:
        self._alarm_overlay.on_alarm_set(key)

    def on_alarm_deleted(self, key: str) -> None:
        self._alarm_overlay.on_alarm_deleted(key)
