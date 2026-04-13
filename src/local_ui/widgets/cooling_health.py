"""Cooling Health diagram widget.

Loads cooling_health.svg as a template and substitutes {PLACEHOLDER} values
and {PLACEHOLDER_C} color values each time a sensor update is received.

Value placeholders: {INLET_1}, {OUTLET_1}, {PUMP_DUTY_1}, etc.
Color placeholders: {INLET_1_C}, {OUTLET_1_C}, etc.
  — resolved against thresholds from docs/threshold.md
  — normal=#27ae60  warning=#e67e22  critical=#e74c3c  no-data=#9e9e9e
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

_SVG_PATH = Path(__file__).parent.parent / "assets" / "cooling_health.svg"

# ── Color constants ────────────────────────────────────────────────────────────
_C_NORMAL   = "#27ae60"
_C_WARNING  = "#e67e22"
_C_CRITICAL = "#e74c3c"
_C_NO_DATA  = "#9e9e9e"


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


def _color_delta(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > 20:
        return _C_CRITICAL
    if v > 15:
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
    if s == "LEAKED":
        return _C_CRITICAL
    if s == "NORMAL":
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
    # Sensor values
    "INLET_1": "--", "INLET_2": "--",
    "OUTLET_1": "--", "OUTLET_2": "--",
    "DELTA_1": "--", "DELTA_2": "--",
    "PUMP_DUTY_1": "--", "PUMP_DUTY_2": "--",
    "FAN_DUTY_1": "--", "FAN_DUTY_2": "--",
    "FLOW_1": "--", "FLOW_2": "--",
    "WATER_LEVEL": "--",
    "PH": "--", "CONDUCTIVITY": "--",
    "LEAK": "--",
    "AMBIENT_TEMP": "--", "AMBIENT_HUM": "--",
    "PRESSURE": "--",
    # Color placeholders (default: no-data gray)
    "INLET_1_C":      _C_NO_DATA,
    "INLET_2_C":      _C_NO_DATA,
    "OUTLET_1_C":     _C_NO_DATA,
    "OUTLET_2_C":     _C_NO_DATA,
    "DELTA_1_C":      _C_NO_DATA,
    "DELTA_2_C":      _C_NO_DATA,
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
        self._svg_template: str = _SVG_PATH.read_text(encoding="utf-8")
        self._build_ui()
        self._reload_svg()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._svg_widget = QSvgWidget()
        self._svg_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._svg_widget)

    # ------------------------------------------------------------------
    # Signal handlers

    def on_sensor_updated(self, key: str, value: str) -> None:
        placeholder = _KEY_TO_PLACEHOLDER.get(key)
        if placeholder is None:
            return
        try:
            formatted = f"{float(value):.1f}"
        except ValueError:
            formatted = value
        self._values[placeholder] = formatted
        self._update_water_level()
        self._update_deltas()
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

    def _update_deltas(self) -> None:
        for loop in ("1", "2"):
            try:
                outlet = float(self._values[f"OUTLET_{loop}"])
                inlet  = float(self._values[f"INLET_{loop}"])
                self._values[f"DELTA_{loop}"] = f"{outlet - inlet:.1f}"
            except (ValueError, KeyError):
                pass

    def _update_colors(self) -> None:
        v = self._values
        v["INLET_1_C"]      = _color_inlet_temp(v["INLET_1"])
        v["INLET_2_C"]      = _color_inlet_temp(v["INLET_2"])
        v["OUTLET_1_C"]     = _color_outlet_temp(v["OUTLET_1"])
        v["OUTLET_2_C"]     = _color_outlet_temp(v["OUTLET_2"])
        v["DELTA_1_C"]      = _color_delta(v["DELTA_1"])
        v["DELTA_2_C"]      = _color_delta(v["DELTA_2"])
        v["WATER_LEVEL_C"]  = _color_water_level(v["WATER_LEVEL"])
        v["LEAK_C"]         = _color_leak(v["LEAK"])
        v["AMBIENT_TEMP_C"] = _color_ambient_temp(v["AMBIENT_TEMP"])
        v["AMBIENT_HUM_C"]  = _color_ambient_hum(v["AMBIENT_HUM"])

    # ------------------------------------------------------------------
    # SVG reload

    def _reload_svg(self) -> None:
        svg = self._svg_template
        for placeholder, value in self._values.items():
            svg = svg.replace(f"{{{placeholder}}}", value)
        self._svg_widget.load(QByteArray(svg.encode("utf-8")))
