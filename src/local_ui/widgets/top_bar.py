"""Top bar widget.

Layout (left → center → right):
  Left  : [Monitoring] [History] tab buttons
  Center: [🔔 N]  IP: x.x.x.x  System: <bold colored>  Link: <bold colored>  [Manual/Auto/Emergency]
  Right : HH:MM:SS

Design rules (from UI_Design.md):
  - White background
  - Tab buttons: slightly enlarged, active tab highlighted
  - Alarm badge: hidden when 0 alarms, orange=Warning / red=Critical
  - System / Link: plain text — label regular, value bold + color coded
  - Mode button: Manual=white/dark, Auto=blue, Emergency=red
  - No badge/button shapes for System or Link
"""

from __future__ import annotations

import datetime
import fcntl
import logging
import os
import socket
import struct

import redis
from PySide6.QtCore import QPropertyAnimation, QTimer, Qt, Signal, Property, QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

log = logging.getLogger(__name__)

_SIOCGIFADDR = 0x8915
_IP_REFRESH_INTERVAL_MS = 30_000

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

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
_BADGE_NORMAL_STYLE = (
    "QPushButton { background:#ffffff; color:#000000; border-radius:14px;"
    " padding:4px 14px; font-size:15pt; font-weight:bold;"
    " border:2px solid #000000; }"
)
_BADGE_WARNING_STYLE  = (
    "QPushButton { background:#e67e22; color:white; border-radius:14px;"
    " padding:4px 14px; font-size:15pt; font-weight:bold; border:none; }"
)
_BADGE_CRITICAL_STYLE = (
    "QPushButton { background:#e74c3c; color:white; border-radius:14px;"
    " padding:4px 14px; font-size:15pt; font-weight:bold; border:none; }"
)

# ── Tab button styles ──────────────────────────────────────────────────────────
_TAB_ACTIVE_STYLE = (
    "QPushButton { background:#2c3e50; color:white; border:2px solid transparent;"
    " padding:6px 16px; font-size:15pt; font-weight:bold; border-radius:4px; }"
)
_TAB_INACTIVE_STYLE = (
    "QPushButton { background:#ecf0f1; color:#2c3e50; border:2px solid transparent;"
    " padding:6px 16px; font-size:15pt; font-weight:bold; border-radius:4px; }"
    "QPushButton:hover { background:#d5dbdb; }"
)

# ── Toggle switch widget ──────────────────────────────────────────────────────

class ToggleSwitch(QWidget):
    """Sliding toggle switch with ON/OFF labels."""

    toggled = Signal(bool)

    _TRACK_W = 140
    _TRACK_H = 36
    _KNOB_R = 14
    _KNOB_MARGIN = 4

    _COLOR_ON = QColor("#27ae60")
    _COLOR_OFF = QColor("#3498db")
    _COLOR_EMERGENCY = QColor("#e74c3c")
    _COLOR_KNOB = QColor("#ffffff")

    def __init__(self, checked: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._emergency = False
        self._knob_x = float(self._on_x() if checked else self._off_x())
        self.setFixedSize(self._TRACK_W, self._TRACK_H)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"knob_x")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def _on_x(self) -> float:
        return float(self._TRACK_W - self._KNOB_MARGIN - self._KNOB_R * 2)

    def _off_x(self) -> float:
        return float(self._KNOB_MARGIN)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, on: bool) -> None:
        if self._emergency:
            return
        self._checked = on
        self._animate(self._on_x() if on else self._off_x())
        self.update()

    def set_emergency(self, em: bool) -> None:
        self._emergency = em
        if em:
            self._checked = False
            self._animate(self._off_x())
        self.update()

    def _animate(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob_x)
        self._anim.setEndValue(target)
        self._anim.start()

    def _get_knob_x(self) -> float:
        return self._knob_x

    def _set_knob_x(self, v: float) -> None:
        self._knob_x = v
        self.update()

    knob_x = Property(float, _get_knob_x, _set_knob_x)

    def mousePressEvent(self, event) -> None:
        if self._emergency:
            self._emergency = False
            self._checked = False
            self._animate(self._off_x())
            self.toggled.emit(False)
            self.update()
            return
        self._checked = not self._checked
        self._animate(self._on_x() if self._checked else self._off_x())
        self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Track
        if self._emergency:
            track_color = self._COLOR_EMERGENCY
        elif self._checked:
            track_color = self._COLOR_ON
        else:
            track_color = self._COLOR_OFF

        r = self._TRACK_H / 2
        p.setPen(Qt.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(0, 0, self._TRACK_W, self._TRACK_H, r, r)

        # Label
        label_font = QFont()
        label_font.setPointSize(15)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QPen(self._COLOR_KNOB))

        knob_w = self._KNOB_R * 2 + self._KNOB_MARGIN * 2
        if self._emergency:
            p.drawText(self.rect(), Qt.AlignCenter, "STOP")
        elif self._checked:
            # Knob is on right — text area is left side
            p.drawText(0, 0, self._TRACK_W - knob_w, self._TRACK_H, Qt.AlignCenter, "Auto")
        else:
            # Knob is on left — text area is right side
            p.drawText(knob_w, 0, self._TRACK_W - knob_w, self._TRACK_H, Qt.AlignCenter, "Manual")

        # Knob
        p.setPen(Qt.NoPen)
        p.setBrush(self._COLOR_KNOB)
        cy = self._TRACK_H / 2
        p.drawEllipse(int(self._knob_x), int(cy - self._KNOB_R),
                       self._KNOB_R * 2, self._KNOB_R * 2)
        p.end()


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
        self._redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        self.setStyleSheet("background:#ffffff;")
        self._build_ui()
        self._sync_mode_from_redis()
        self._start_timers()

    def _sync_mode_from_redis(self) -> None:
        # main.py ran SETNX before widgets were built, so the key is expected
        # to exist. Fall back to "auto" if Redis is unreachable.
        try:
            raw = self._redis.get("control:mode")
            mode = raw.decode() if isinstance(raw, bytes) else (raw or "auto")
        except Exception as e:
            log.warning("Could not read control:mode from Redis: %s", e)
            mode = "auto"
        self.on_mode_updated(mode)

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
            btn.setMinimumHeight(52)
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
        center_layout.setSpacing(0)
        center_layout.setAlignment(Qt.AlignCenter)

        def _sep() -> QLabel:
            s = QLabel("|")
            s.setStyleSheet("color:#9e9e9e; font-size:15pt; padding:0 6px;")
            s.setAlignment(Qt.AlignVCenter)
            return s

        # Alarm badge
        self._alarm_badge = QPushButton("🔔 -")
        self._alarm_badge.setMinimumSize(90, 44)
        self._alarm_badge.setCursor(Qt.PointingHandCursor)
        self._alarm_badge.setStyleSheet(_BADGE_NORMAL_STYLE)
        self._alarm_badge.clicked.connect(self.bell_tapped)
        center_layout.addWidget(self._alarm_badge)

        center_layout.addWidget(_sep())

        # IP
        ip_font = QFont()
        ip_font.setPointSize(15)
        self._ip_label = QLabel("IP: --")
        self._ip_label.setFont(ip_font)
        self._ip_label.setStyleSheet("color:#000000;")
        center_layout.addWidget(self._ip_label)

        center_layout.addWidget(_sep())

        # System status
        self._system_label = self._make_status_label("System:", "Normal", _SYSTEM_COLORS["Normal"])
        center_layout.addWidget(self._system_label)

        center_layout.addWidget(_sep())

        # Link status
        self._link_label = self._make_status_label("Link:", "ok", _LINK_COLORS["ok"])
        center_layout.addWidget(self._link_label)

        center_layout.addWidget(_sep())

        # Mode toggle switch (default: Auto = ON)
        self._mode_switch = ToggleSwitch(checked=True)
        self._mode_switch.toggled.connect(self._on_mode_toggled)
        self._current_mode = "auto"
        center_layout.addWidget(self._mode_switch)

        layout.addWidget(center)

        # ── Right: clock ───────────────────────────────────────────────
        clock_font = QFont()
        clock_font.setPointSize(17)
        self._clock_label = QLabel()
        self._clock_label.setFont(clock_font)
        self._clock_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self._clock_label.setStyleSheet("color:#000000; padding:0 16px;")
        layout.addWidget(self._clock_label)

        self._switch_tab(0)
        self._refresh_ip()

    def _make_status_label(self, prefix: str, value: str, color: str) -> QLabel:
        """Return a QLabel showing 'prefix <bold colored value>'."""
        lbl = QLabel()
        lbl.setTextFormat(Qt.RichText)
        lbl.setText(
            f'<span style="color:#000000; font-size:15pt;">{prefix} </span>'
            f'<span style="color:{color}; font-size:15pt; font-weight:bold;">{value}</span>'
        )
        return lbl

    def _set_status_text(self, label: QLabel, prefix: str, value: str, color: str) -> None:
        label.setText(
            f'<span style="color:#000000; font-size:15pt;">{prefix} </span>'
            f'<span style="color:{color}; font-size:15pt; font-weight:bold;">{value}</span>'
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
    # Mode button

    def _on_mode_toggled(self, checked: bool) -> None:
        # UI owns control:mode: write directly to Redis and publish so other
        # subscribers (and this process's own subscriber) see the change.
        mode = "auto" if checked else "manual"
        self._current_mode = mode
        try:
            pipe = self._redis.pipeline()
            pipe.set("control:mode", mode)
            pipe.publish("control:mode", mode)
            pipe.execute()
            log.info("control:mode → %s", mode)
        except Exception as e:
            log.warning("Could not write control:mode to Redis: %s", e)

    def on_mode_updated(self, mode: str) -> None:
        """Update toggle switch display. Called when control:mode changes."""
        self._current_mode = mode
        if mode == "emergency":
            self._mode_switch.set_emergency(True)
        elif mode == "auto":
            self._mode_switch.set_emergency(False)
            self._mode_switch.set_checked(True)
        else:
            self._mode_switch.set_emergency(False)
            self._mode_switch.set_checked(False)

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
        elif any("critical" in k or k == "alarm:leak_detected" or "disconnected" in k
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
            self._alarm_badge.setText("🔔 -")
            self._alarm_badge.setStyleSheet(_BADGE_NORMAL_STYLE)
            return
        has_critical = any(
            "critical" in k or k == "alarm:leak_detected" or "disconnected" in k
            for k in self._active_alarms
        )
        self._alarm_badge.setText(f"🔔 {count}")
        self._alarm_badge.setStyleSheet(
            _BADGE_CRITICAL_STYLE if has_critical else _BADGE_WARNING_STYLE
        )
