"""Cooling Health diagram widget.

Loads cooling_health.svg as a template and substitutes {PLACEHOLDER} values
and {PLACEHOLDER_C} color values each time a sensor update is received.

Value placeholders: {INLET_1}, {OUTLET_1}, {PUMP_DUTY_1}, etc.
Color placeholders: {INLET_1_C}, {OUTLET_1_C}, etc.
  — resolved against thresholds from docs/threshold.md
  — normal=#27ae60  warning=#e67e22  critical=#e74c3c  no-data=#9e9e9e

Pump/Fan inline control:
  Transparent QPushButton overlays are positioned over the SVG.
  Tapping opens NumpadDialog → Apply sends to Redis (fake) or MCG (real).

  NOTE: Overlay positions (_OVERLAY_POSITIONS) are defined as fractions of
  widget size and must be calibrated after cooling_health.svg is finalized.
"""

from __future__ import annotations

import logging

import redis
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QFont
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QDialog,
    QSizePolicy,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.local_ui.widgets.control_panel import NumpadDialog

log = logging.getLogger(__name__)

_SVG_PATH = Path(__file__).parent.parent / "assets" / "cooling_health.svg"

REDIS_HOST = "localhost"
REDIS_PORT  = 6379
REDIS_DB    = 0

# ── Color constants ────────────────────────────────────────────────────────────
_C_NORMAL   = "#27ae60"
_C_WARNING  = "#e67e22"
_C_CRITICAL = "#e74c3c"
_C_NO_DATA  = "#000000"  # 원칙 2: 회색 금지 — no-data는 검정으로, 값 "--"로 구분

# ── Overlay button relative positions (x, y, w, h) as fractions of widget size ─
# Calibrated to cooling_health.svg layout (SVG canvas: 1280×608).
# Pump:    x=222-342, y=120-215  →  rx=222/1280, ry=120/608, rw=120/1280, rh=95/608
# Fan+Rad: x=1095-1265, y=120-215 → rx=1095/1280, ry=120/608, rw=170/1280, rh=95/608
_OVERLAY_POSITIONS: dict[str, tuple[float, float, float, float]] = {
    "pump1": (0.164, 0.270, 0.094, 0.181),  # Pump Loop1 (x=210,y=164,w=120,h=110)
    "pump2": (0.164, 0.549, 0.094, 0.181),  # Pump Loop2 (x=210,y=334,w=120,h=110)
    "fan1":  (0.867, 0.270, 0.102, 0.181),  # Fan+Rad Loop1 (x=1110,y=164,w=130,h=110)
    "fan2":  (0.867, 0.549, 0.102, 0.181),  # Fan+Rad Loop2 (x=1110,y=334,w=130,h=110)
}
# Note: Server box positions for reference (not overlay buttons)
# Server1: x=771-871, y=20-75  / Server2: x=771-871, y=523-578

_DUTY_KEYS: dict[str, str] = {
    "pump1": "sensor:pump_pwm_duty_1",
    "pump2": "sensor:pump_pwm_duty_2",
    "fan1":  "sensor:fan_pwm_duty_1",
    "fan2":  "sensor:fan_pwm_duty_2",
}


# ── Threshold functions ────────────────────────────────────────────────────────

def _color_inlet_temp(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > 45 or v < 18:
        return _C_CRITICAL
    if v > 40 or v < 22:
        return _C_WARNING
    return _C_NORMAL


def _color_outlet_temp(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > 65 or v < 18:
        return _C_CRITICAL
    if v > 60 or v < 22:
        return _C_WARNING
    return _C_NORMAL


def _color_water_level(s: str) -> str:
    if s == "HIGH":
        return _C_NORMAL
    if s == "MIDDLE":
        return _C_WARNING
    if s == "LOW":
        return _C_CRITICAL
    return _C_NO_DATA


def _color_leak(s: str) -> str:
    # s is already transformed: "None" or "Detected"
    if s == "Detected":
        return _C_CRITICAL
    if s == "None":
        return _C_NORMAL
    return _C_NO_DATA


def _color_ambient_temp(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > 50:
        return _C_CRITICAL
    if v > 40:
        return _C_WARNING
    return _C_NORMAL


def _color_ambient_hum(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > 80 or v < 10:
        return _C_CRITICAL
    if v > 60:
        return _C_WARNING
    return _C_NORMAL


# ── Default values & colors ────────────────────────────────────────────────────

_DEFAULT_VALUES: dict[str, str] = {
    "INLET_1": "--", "INLET_2": "--",
    "OUTLET_1": "--", "OUTLET_2": "--",
    "PUMP_DUTY_1": "--", "PUMP_DUTY_2": "--",
    "FAN_DUTY_1": "--", "FAN_DUTY_2": "--",
    "FLOW_1": "--", "FLOW_2": "--",
    "WATER_LEVEL": "--",
    "PH": "--", "CONDUCTIVITY": "--",
    "LEAK": "--",
    "AMBIENT_TEMP": "--", "AMBIENT_HUM": "--",
    "PRESSURE": "--",
    # Color placeholders
    "INLET_1_C":      _C_NO_DATA,
    "INLET_2_C":      _C_NO_DATA,
    "OUTLET_1_C":     _C_NO_DATA,
    "OUTLET_2_C":     _C_NO_DATA,
    "WATER_LEVEL_C":  _C_NO_DATA,
    "LEAK_C":         _C_NO_DATA,
    "AMBIENT_TEMP_C": _C_NO_DATA,
    "AMBIENT_HUM_C":  _C_NO_DATA,
}

# Redis key → SVG value placeholder
_KEY_TO_PLACEHOLDER: dict[str, str] = {
    "sensor:coolant_temp_inlet_1":  "INLET_1",
    "sensor:coolant_temp_inlet_2":  "INLET_2",
    "sensor:coolant_temp_outlet_1": "OUTLET_1",
    "sensor:coolant_temp_outlet_2": "OUTLET_2",
    "sensor:pump_pwm_duty_1":       "PUMP_DUTY_1",
    "sensor:pump_pwm_duty_2":       "PUMP_DUTY_2",
    "sensor:fan_pwm_duty_1":        "FAN_DUTY_1",
    "sensor:fan_pwm_duty_2":        "FAN_DUTY_2",
    "sensor:flow_rate_1":           "FLOW_1",
    "sensor:flow_rate_2":           "FLOW_2",
    "sensor:ph":                    "PH",
    "sensor:conductivity":          "CONDUCTIVITY",
    "sensor:leak":                  "LEAK",
    "sensor:ambient_temp":          "AMBIENT_TEMP",
    "sensor:ambient_humidity":      "AMBIENT_HUM",
    "sensor:pressure":              "PRESSURE",
}


class CoolingHealthWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: dict[str, str] = dict(_DEFAULT_VALUES)
        self._current_duty: dict[str, int] = {k: 0 for k in _DUTY_KEYS}
        self._redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        self._overlay_btns: dict[str, QPushButton] = {}

        try:
            self._svg_template: str = _SVG_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            log.warning("cooling_health.svg not found at %s — diagram will be empty", _SVG_PATH)
            self._svg_template = ""

        self._build_ui()
        self._build_overlays()
        self._reload_svg()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._svg_widget = QSvgWidget()
        self._svg_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._svg_widget)

    def _build_overlays(self) -> None:
        """Create transparent touch-target buttons over Pump/Fan SVG nodes."""
        btn_font = QFont()
        btn_font.setPointSize(1)  # invisible text, button is transparent

        for slot in _OVERLAY_POSITIONS:
            btn = QPushButton("", self)
            btn.setStyleSheet(
                "QPushButton { background:transparent; border:none; }"
                "QPushButton:pressed { background:rgba(0,0,0,0.05); }"
            )
            btn.setFont(btn_font)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, s=slot: self._on_overlay_tap(s))
            btn.raise_()
            self._overlay_btns[slot] = btn

        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return
        for slot, (rx, ry, rw, rh) in _OVERLAY_POSITIONS.items():
            btn = self._overlay_btns[slot]
            btn.setGeometry(
                int(rx * w), int(ry * h),
                int(rw * w), int(rh * h),
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_overlays()

    # ------------------------------------------------------------------
    # Overlay tap handler

    def _on_overlay_tap(self, slot: str) -> None:
        current = self._current_duty.get(slot, 0)
        dlg = NumpadDialog(current, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_val = dlg.value()
            self._apply_duty(slot, new_val)

    def _apply_duty(self, slot: str, value: int) -> None:
        redis_key = _DUTY_KEYS[slot]
        try:
            pipe = self._redis.pipeline()
            pipe.set(redis_key, str(value))
            pipe.publish(redis_key, str(value))
            pipe.execute()
            self._current_duty[slot] = value
            log.info("Set %s = %d%%", redis_key, value)
        except Exception as exc:
            log.error("Redis write failed for %s: %s", redis_key, exc)

    # ------------------------------------------------------------------
    # Signal handlers

    def on_sensor_updated(self, key: str, value: str) -> None:
        placeholder = _KEY_TO_PLACEHOLDER.get(key)
        if placeholder is None:
            return

        # Track current duty values for numpad pre-fill
        if key in _DUTY_KEYS.values():
            for slot, rkey in _DUTY_KEYS.items():
                if key == rkey:
                    try:
                        self._current_duty[slot] = int(float(value))
                    except ValueError:
                        pass

        # Transform leak display value
        if key == "sensor:leak":
            self._values["LEAK"] = "None" if value == "NORMAL" else "Detected"
        else:
            try:
                self._values[placeholder] = f"{float(value):.1f}"
            except ValueError:
                self._values[placeholder] = value

        self._update_water_level()
        self._update_colors()
        self._reload_svg()

    def on_water_level_high(self, value: str) -> None:
        self._values["_water_high"] = value
        self._update_water_level()
        self._update_colors()
        self._reload_svg()

    def on_water_level_low(self, value: str) -> None:
        self._values["_water_low"] = value
        self._update_water_level()
        self._update_colors()
        self._reload_svg()

    # ------------------------------------------------------------------
    # Computed values

    def _update_water_level(self) -> None:
        high = self._values.get("_water_high", "1")
        low  = self._values.get("_water_low",  "1")
        if high == "1" and low == "1":
            self._values["WATER_LEVEL"] = "HIGH"
        elif high == "0" and low == "1":
            self._values["WATER_LEVEL"] = "MIDDLE"
        else:
            self._values["WATER_LEVEL"] = "LOW"

    def _update_colors(self) -> None:
        v = self._values
        v["INLET_1_C"]      = _color_inlet_temp(v["INLET_1"])
        v["INLET_2_C"]      = _color_inlet_temp(v["INLET_2"])
        v["OUTLET_1_C"]     = _color_outlet_temp(v["OUTLET_1"])
        v["OUTLET_2_C"]     = _color_outlet_temp(v["OUTLET_2"])
        v["WATER_LEVEL_C"]  = _color_water_level(v["WATER_LEVEL"])
        v["LEAK_C"]         = _color_leak(v["LEAK"])
        v["AMBIENT_TEMP_C"] = _color_ambient_temp(v["AMBIENT_TEMP"])
        v["AMBIENT_HUM_C"]  = _color_ambient_hum(v["AMBIENT_HUM"])

    # ------------------------------------------------------------------
    # SVG reload

    def _reload_svg(self) -> None:
        if not self._svg_template:
            return
        svg = self._svg_template
        for placeholder, value in self._values.items():
            if not placeholder.startswith("_"):
                svg = svg.replace(f"{{{placeholder}}}", value)
        self._svg_widget.load(QByteArray(svg.encode("utf-8")))
