"""Top bar widget.

Layout (left → right):
  [Monitoring] [History]          [System badge]  [Link badge]  [HH:MM:SS]

System badge logic:
  comm disconnected → "-"   (grey)
  critical alarm present  → "Critical"  (red)
  warning alarm present   → "Warning"   (yellow)
  else                    → "Normal"    (green)

Link badge:
  Displays comm:status value directly: ok | timeout | disconnected
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from PySide6.QtGui import QFont
import datetime


_SYSTEM_BADGE_STYLES: dict[str, str] = {
    "Normal":       "background:#27ae60; color:white; border-radius:6px; padding:4px 12px;",
    "Warning":      "background:#f39c12; color:white; border-radius:6px; padding:4px 12px;",
    "Critical":     "background:#c0392b; color:white; border-radius:6px; padding:4px 12px;",
    "-":            "background:#7f8c8d; color:white; border-radius:6px; padding:4px 12px;",
}

_LINK_BADGE_STYLES: dict[str, str] = {
    "ok":           "background:#27ae60; color:white; border-radius:6px; padding:4px 12px;",
    "timeout":      "background:#f39c12; color:white; border-radius:6px; padding:4px 12px;",
    "disconnected": "background:#c0392b; color:white; border-radius:6px; padding:4px 12px;",
}

_TAB_ACTIVE_STYLE   = "background:#2c3e50; color:white;  border:none; padding:8px 20px; font-size:15px;"
_TAB_INACTIVE_STYLE = "background:#bdc3c7; color:#2c3e50; border:none; padding:8px 20px; font-size:15px;"


class TopBarWidget(QWidget):
    def __init__(self, stacked_widget, parent=None) -> None:
        super().__init__(parent)
        self._stacked = stacked_widget
        self._active_alarms: set[str] = set()
        self._link_status = "ok"

        self._build_ui()
        self._start_clock()

    # ------------------------------------------------------------------
    # UI construction

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._btn_monitoring = QPushButton("Monitoring")
        self._btn_history    = QPushButton("History")
        for btn in (self._btn_monitoring, self._btn_history):
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
        self._btn_monitoring.clicked.connect(lambda: self._switch_tab(0))
        self._btn_history.clicked.connect(lambda: self._switch_tab(1))

        layout.addWidget(self._btn_monitoring)
        layout.addWidget(self._btn_history)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(spacer)

        badge_font = QFont()
        badge_font.setPointSize(13)
        badge_font.setBold(True)

        self._system_badge = QLabel("Normal")
        self._system_badge.setFont(badge_font)
        self._system_badge.setAlignment(Qt.AlignCenter)

        self._link_badge = QLabel("ok")
        self._link_badge.setFont(badge_font)
        self._link_badge.setAlignment(Qt.AlignCenter)

        self._clock_label = QLabel()
        clock_font = QFont()
        clock_font.setPointSize(14)
        self._clock_label.setFont(clock_font)
        self._clock_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._system_badge)
        layout.addWidget(self._link_badge)
        layout.addWidget(self._clock_label)

        self._switch_tab(0)
        self._refresh_system_badge()
        self._refresh_link_badge("ok")

    # ------------------------------------------------------------------
    # Tab switching

    def _switch_tab(self, index: int) -> None:
        self._stacked.setCurrentIndex(index)
        self._btn_monitoring.setStyleSheet(
            _TAB_ACTIVE_STYLE if index == 0 else _TAB_INACTIVE_STYLE
        )
        self._btn_history.setStyleSheet(
            _TAB_ACTIVE_STYLE if index == 1 else _TAB_INACTIVE_STYLE
        )

    # ------------------------------------------------------------------
    # Clock

    def _start_clock(self) -> None:
        self._tick()
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)

    def _tick(self) -> None:
        self._clock_label.setText(
            datetime.datetime.now().strftime("%H:%M:%S")
        )

    # ------------------------------------------------------------------
    # Badge update (called by main window via signals)

    def on_comm_updated(self, key: str, value: str) -> None:
        if key == "comm:status":
            self._link_status = value
            self._refresh_link_badge(value)
            self._refresh_system_badge()

    def on_alarm_set(self, alarm_key: str) -> None:
        self._active_alarms.add(alarm_key)
        self._refresh_system_badge()

    def on_alarm_deleted(self, alarm_key: str) -> None:
        self._active_alarms.discard(alarm_key)
        self._refresh_system_badge()

    # ------------------------------------------------------------------
    # Internal refresh helpers

    def _refresh_system_badge(self) -> None:
        if self._link_status == "disconnected":
            state = "-"
        elif any("critical" in k for k in self._active_alarms):
            state = "Critical"
        elif self._active_alarms:
            state = "Warning"
        else:
            state = "Normal"

        self._system_badge.setText(state)
        self._system_badge.setStyleSheet(_SYSTEM_BADGE_STYLES.get(state, ""))

    def _refresh_link_badge(self, status: str) -> None:
        self._link_badge.setText(status)
        self._link_badge.setStyleSheet(
            _LINK_BADGE_STYLES.get(status, _LINK_BADGE_STYLES["disconnected"])
        )
