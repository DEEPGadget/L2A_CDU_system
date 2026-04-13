"""Cooling Health diagram widget.

Loads cooling_health.svg as a template and substitutes {PLACEHOLDER} values
each time a sensor update is received. The updated SVG is reloaded into
QSvgWidget so the display refreshes instantly.

Placeholders in the SVG:
  {INLET_1}, {INLET_2}     — coolant inlet temperature (°C)
  {OUTLET_1}, {OUTLET_2}   — coolant outlet temperature (°C)
  {DELTA_1}, {DELTA_2}     — ΔT (outlet − inlet, computed here)
  {PUMP_DUTY_1}, {PUMP_DUTY_2}
  {FAN_DUTY_1}, {FAN_DUTY_2}
  {FLOW_1}, {FLOW_2}
  {WATER_LEVEL}            — HIGH / MIDDLE / LOW
  {PH}, {CONDUCTIVITY}
  {LEAK}                   — NORMAL / LEAKED
  {AMBIENT_TEMP}, {AMBIENT_HUM}
  {PRESSURE}
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

_SVG_PATH = Path(__file__).parent.parent / "assets" / "cooling_health.svg"

_DEFAULT_VALUES: dict[str, str] = {
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
}

# Map Redis key → SVG placeholder
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
    # Signal handler

    def on_sensor_updated(self, key: str, value: str) -> None:
        placeholder = _KEY_TO_PLACEHOLDER.get(key)
        if placeholder is None:
            return

        # Format float values to 1 decimal place
        try:
            formatted = f"{float(value):.1f}"
        except ValueError:
            formatted = value

        self._values[placeholder] = formatted
        self._update_water_level()
        self._update_deltas()
        self._reload_svg()

    # ------------------------------------------------------------------
    # Computed values

    def _update_water_level(self) -> None:
        """Convert water_level_high / water_level_low bits → label."""
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

    # ------------------------------------------------------------------
    # SVG reload

    def _reload_svg(self) -> None:
        svg = self._svg_template
        for placeholder, value in self._values.items():
            svg = svg.replace(f"{{{placeholder}}}", value)
        self._svg_widget.load(QByteArray(svg.encode("utf-8")))

    # ------------------------------------------------------------------
    # Water level raw key (not in standard _KEY_TO_PLACEHOLDER)

    def on_water_level_high(self, value: str) -> None:
        self._values["_water_high"] = value
        self._update_water_level()
        self._reload_svg()

    def on_water_level_low(self, value: str) -> None:
        self._values["_water_low"] = value
        self._update_water_level()
        self._reload_svg()
