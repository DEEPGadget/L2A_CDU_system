"""Top bar widget.

Layout (left → center → right):
  Left  : [Monitoring] [History] tab buttons
  Center: [🔔 N]  IP: x.x.x.x  System: <bold colored>  Link: <bold colored>
  Right : HH:MM:SS

Design rules (from UI_Design.md):
  - White background
  - Tab buttons: slightly enlarged, active tab highlighted
  - Alarm badge: hidden when 0 alarms, orange=Warning / red=Critical
  - System / Link: plain text — label regular, value bold + color coded
  - No badge/button shapes for System or Link
"""

from __future__ import annotations

import datetime
import fcntl
import os
import socket
import struct

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

_SIOCGIFADDR = 0x8915
_IP_REFRESH_INTERVAL_MS = 30_000

# ── Status text colors ─────────────────────────────────────────────────────────
_SYSTEM_COLORS: dict[str, str] = {
    "Normal":   "#27ae60",
    "Warning":  "#e67e22",
    "Critical": "#e74c3c",
    "-":        "#000000",
}

_LINK_COLORS: dict[str, str] = {
    "ok":           "#27ae60",
    "timeout":      "#e67e22",
    "disconnected": "#e74c3c",
}

# ── Alarm badge colors ─────────────────────────────────────────────────────────
_BADGE_WARNING_STYLE  = (
    "QPushButton { background:#e67e22; color:white; border-radius:12px;"
    " padding:2px 10px; font-size:13px; font-weight:bold; border:none; }"
)
_BADGE_CRITICAL_STYLE = (
    "QPushButton { background:#e74c3c; color:white; border-radius:12px;"
    " padding:2px 10px; font-size:13px; font-weight:bold; border:none; }"
)

# ── Tab button styles ──────────────────────────────────────────────────────────
_TAB_ACTIVE_STYLE = (
    "QPushButton { background:#2c3e50; color:white; border:none;"
    " padding:10px 28px; font-size:15px; font-weight:bold; border-radius:4px; }"
)
_TAB_INACTIVE_STYLE = (
    "QPushButton { background:#ecf0f1; color:#2c3e50; border:none;"
    " padding:10px 28px; font-size:15px; border-radius:4px; }"
    "QPushButton:hover { background:#d5dbdb; }"
)


def _iface_ip(iface: str) -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            raw = fcntl.ioctl(
                s.fileno(), _SIOCGIFADDR,
                struct.pack("256s", iface[:15].encode())
            )
            return socket.inet_ntoa(raw[20:24])
    except OSError:
        return None


def get_display_ip() -> str:
    try:
        ifaces = sorted(os.listdir("/sys/class/net/"))
    except OSError:
        return "--"
    for prefix_group in (("eth", "en"), ("wlan", "wl")):
        for iface in ifaces:
            if any(iface.startswith(p) for p in prefix_group):
                ip = _iface_ip(iface)
                if ip and ip != "0.0.0.0":
                    return ip
    return "--"


class TopBarWidget(QWidget):
    bell_tapped = Signal()

    def __init__(self, stacked_widget, parent=None) -> None:
        super().__init__(parent)
        self._stacked = stacked_widget
        self._active_alarms: set[str] = set()
        self._link_status = "ok"
        self.setStyleSheet("background:#ffffff;")
        self._build_ui()
        self._start_timers()

    # ------------------------------------------------------------------
    # UI construction

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 12, 4)
        layout.setSpacing(8)

        # ── Left: tab buttons ──────────────────────────────────────────
        self._btn_monitoring = QPushButton("Monitoring")
        self._btn_history    = QPushButton("History")
        for btn in (self._btn_monitoring, self._btn_history):
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
        self._btn_monitoring.clicked.connect(lambda: self._switch_tab(0))
        self._btn_history.clicked.connect(lambda: self._switch_tab(1))
        layout.addWidget(self._btn_monitoring)
        layout.addWidget(self._btn_history)

        # ── Center: expanding area ─────────────────────────────────────
        center = QWidget()
        center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(20)
        center_layout.setAlignment(Qt.AlignCenter)

        # Alarm badge (hidden when no alarms)
        self._alarm_badge = QPushButton("🔔 0")
        self._alarm_badge.setMinimumSize(64, 32)
        self._alarm_badge.setCursor(Qt.PointingHandCursor)
        self._alarm_badge.setVisible(False)
        self._alarm_badge.clicked.connect(self.bell_tapped)
        center_layout.addWidget(self._alarm_badge)

        # IP
        ip_font = QFont()
        ip_font.setPointSize(12)
        self._ip_label = QLabel("IP: --")
        self._ip_label.setFont(ip_font)
        self._ip_label.setStyleSheet("color:#000000;")
        center_layout.addWidget(self._ip_label)

        # System status
        self._system_label = self._make_status_label("System:", "Normal", _SYSTEM_COLORS["Normal"])
        center_layout.addWidget(self._system_label)

        # Link status
        self._link_label = self._make_status_label("Link:", "ok", _LINK_COLORS["ok"])
        center_layout.addWidget(self._link_label)

        layout.addWidget(center)

        # ── Right: clock ───────────────────────────────────────────────
        clock_font = QFont()
        clock_font.setPointSize(14)
        self._clock_label = QLabel()
        self._clock_label.setFont(clock_font)
        self._clock_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self._clock_label.setStyleSheet("color:#000000;")
        layout.addWidget(self._clock_label)

        self._switch_tab(0)
        self._refresh_ip()

    def _make_status_label(self, prefix: str, value: str, color: str) -> QLabel:
        """Return a QLabel showing 'prefix <bold colored value>'."""
        lbl = QLabel()
        lbl.setTextFormat(Qt.RichText)
        lbl.setText(
            f'<span style="color:#000000; font-size:13px;">{prefix} </span>'
            f'<span style="color:{color}; font-size:13px; font-weight:bold;">{value}</span>'
        )
        return lbl

    def _set_status_text(self, label: QLabel, prefix: str, value: str, color: str) -> None:
        label.setText(
            f'<span style="color:#000000; font-size:13px;">{prefix} </span>'
            f'<span style="color:{color}; font-size:13px; font-weight:bold;">{value}</span>'
        )

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
    # Timers

    def _start_timers(self) -> None:
        self._tick()
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._tick)
        clock_timer.start(1000)

        ip_timer = QTimer(self)
        ip_timer.timeout.connect(self._refresh_ip)
        ip_timer.start(_IP_REFRESH_INTERVAL_MS)

    def _tick(self) -> None:
        self._clock_label.setText(
            datetime.datetime.now().strftime("%H:%M:%S")
        )

    def _refresh_ip(self) -> None:
        self._ip_label.setText(f"IP: {get_display_ip()}")

    # ------------------------------------------------------------------
    # Signal handlers (called by main window)

    def on_comm_updated(self, key: str, value: str) -> None:
        if key == "comm:status":
            self._link_status = value
            self._refresh_link_text(value)
            self._refresh_system_text()

    def on_alarm_set(self, alarm_key: str) -> None:
        self._active_alarms.add(alarm_key)
        self._refresh_system_text()
        self._refresh_alarm_badge()

    def on_alarm_deleted(self, alarm_key: str) -> None:
        self._active_alarms.discard(alarm_key)
        self._refresh_system_text()
        self._refresh_alarm_badge()

    # ------------------------------------------------------------------
    # Internal refresh helpers

    def _refresh_system_text(self) -> None:
        if self._link_status == "disconnected":
            state, color = "-", _SYSTEM_COLORS["-"]
        elif any("critical" in k or "leak" in k or "disconnected" in k
                 for k in self._active_alarms):
            state, color = "Critical", _SYSTEM_COLORS["Critical"]
        elif self._active_alarms:
            state, color = "Warning", _SYSTEM_COLORS["Warning"]
        else:
            state, color = "Normal", _SYSTEM_COLORS["Normal"]
        self._set_status_text(self._system_label, "System:", state, color)

    def _refresh_link_text(self, status: str) -> None:
        color = _LINK_COLORS.get(status, _LINK_COLORS["disconnected"])
        self._set_status_text(self._link_label, "Link:", status, color)

    def _refresh_alarm_badge(self) -> None:
        count = len(self._active_alarms)
        if count == 0:
            self._alarm_badge.setVisible(False)
            return
        has_critical = any(
            "critical" in k or "leak" in k or "disconnected" in k
            for k in self._active_alarms
        )
        self._alarm_badge.setText(f"🔔 {count}")
        self._alarm_badge.setStyleSheet(
            _BADGE_CRITICAL_STYLE if has_critical else _BADGE_WARNING_STYLE
        )
        self._alarm_badge.setVisible(True)
