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

  Mode gating (docs/UI_Design.md §1-1):
    - Manual mode: overlays enabled, {GEAR} placeholder → "⚙"
    - Auto mode:   overlays disabled, {GEAR} → "" (icon hidden),
                   _apply_duty blocked as a defensive guard.

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
from src import thresholds as T

log = logging.getLogger(__name__)

_SVG_PATH = Path(__file__).parent.parent / "assets" / "cooling_health.svg"

REDIS_HOST = "localhost"
REDIS_PORT  = 6379
REDIS_DB    = 0

# ── Color constants ────────────────────────────────────────────────────────────
_C_NORMAL   = "#27ae60"
_C_WARNING  = "#e67e22"
_C_CRITICAL = "#e74c3c"
_C_NO_DATA  = "#000000"  # no-data renders as black; value shown as "--" to distinguish from a real reading

# ── Overlay button relative positions (x, y, w, h) as fractions of widget size ─
# Calibrated to cooling_health.svg layout (SVG canvas: 1280×608).
# Pump:    rect x=225, y=135, w=120, h=150  → rx=225/1280, ry=135/608, rw=120/1280, rh=150/608
# Fan+Rad: rect x=1095, y=60, w=160, h=220 (L1) / y=320 (L2) — L1 위로 L2 아래로 분리
# Loop2 y offset: y=320 → ry=320/608
_OVERLAY_POSITIONS: dict[str, tuple[float, float, float, float]] = {
    "pump1": (0.176, 0.222, 0.094, 0.247),  # Pump Loop1    (x=225, y=135, w=120, h=150)
    "pump2": (0.176, 0.518, 0.094, 0.247),  # Pump Loop2    (x=225, y=315, w=120, h=150)
    "fan1":  (0.855, 0.099, 0.125, 0.362),  # Fan+Rad Loop1 (x=1095,y=60,  w=160, h=220)
    "fan2":  (0.855, 0.526, 0.125, 0.362),  # Fan+Rad Loop2 (x=1095,y=320, w=160, h=220)
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
    if v > T.INLET_TEMP_CRIT_HI or v < T.INLET_TEMP_CRIT_LO:
        return _C_CRITICAL
    if v > T.INLET_TEMP_NORMAL_HI or v < T.INLET_TEMP_NORMAL_LO:
        return _C_WARNING
    return _C_NORMAL


def _color_outlet_temp(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > T.OUTLET_TEMP_CRIT_HI or v < T.OUTLET_TEMP_CRIT_LO:
        return _C_CRITICAL
    if v > T.OUTLET_TEMP_NORMAL_HI or v < T.OUTLET_TEMP_WARN_LO:
        return _C_WARNING
    return _C_NORMAL


_WATER_LEVEL_MAP: dict[str, str] = {"2": "HIGH", "1": "MIDDLE", "0": "LOW"}


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
    if v > T.AMBIENT_TEMP_CRIT_HI:
        return _C_CRITICAL
    if v > T.AMBIENT_TEMP_WARN_HI:
        return _C_WARNING
    return _C_NORMAL


def _color_ambient_hum(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v > T.AMBIENT_HUM_CRIT_HI or v < T.AMBIENT_HUM_CRIT_LO:
        return _C_CRITICAL
    if v > T.AMBIENT_HUM_WARN_HI:
        return _C_WARNING
    return _C_NORMAL


def _color_ph(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v < T.PH_WARN_LO or v > T.PH_NORMAL_HI:
        return _C_WARNING
    if v < T.PH_NORMAL_LO:
        return _C_WARNING
    return _C_NORMAL


def _color_conductivity(s: str) -> str:
    try:
        v = float(s)
    except (ValueError, TypeError):
        return _C_NO_DATA
    if v < T.CONDUCTIVITY_WARN_LO:
        return _C_WARNING
    return _C_NORMAL


# ── Default values & colors ────────────────────────────────────────────────────

_DEFAULT_VALUES: dict[str, str] = {
    "INLET_1": "--", "INLET_2": "--",
    "OUTLET_1": "--", "OUTLET_2": "--",
    "PUMP_DUTY_1": "--", "PUMP_DUTY_2": "--",
    "FAN_DUTY_1": "--", "FAN_DUTY_2": "--",
    "FAN_RPM_1": "--", "FAN_RPM_2": "--",
    "FLOW_1": "--", "FLOW_2": "--",
    "WATER_LEVEL": "--",
    "PH": "--", "CONDUCTIVITY": "--",
    "LEAK": "--",
    "PH_C":            _C_NO_DATA,
    "CONDUCTIVITY_C":  _C_NO_DATA,
    "AMBIENT_TEMP": "--", "AMBIENT_HUM": "--",
    # Mode-driven gear icon (empty until on_mode_updated fires)
    "GEAR": "",
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
    "sensor:fan_rpm_1":             "FAN_RPM_1",
    "sensor:fan_rpm_2":             "FAN_RPM_2",
    "sensor:flow_rate_1":           "FLOW_1",
    "sensor:flow_rate_2":           "FLOW_2",
    "sensor:water_level":           "WATER_LEVEL",
    "sensor:ph":                    "PH",
    "sensor:conductivity":          "CONDUCTIVITY",
    "sensor:leak":                  "LEAK",
    "sensor:ambient_temp":          "AMBIENT_TEMP",
    "sensor:ambient_humidity":      "AMBIENT_HUM",
}


class CoolingHealthWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: dict[str, str] = dict(_DEFAULT_VALUES)
        self._current_duty: dict[str, int] = {k: 0 for k in _DUTY_KEYS}
        self._current_mode: str = "auto"
        self._redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        self._overlay_btns: dict[str, QPushButton] = {}

        try:
            self._svg_template: str = _SVG_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            log.warning("cooling_health.svg not found at %s — diagram will be empty", _SVG_PATH)
            self._svg_template = ""

        self._build_ui()
        self._build_overlays()
        self._load_initial_values()
        self._load_initial_mode()

    def _load_initial_values(self) -> None:
        """Read current sensor values from Redis on startup.

        Pub/Sub is fire-and-forget: if the simulator's initial publish fires
        before the subscriber connects, the message is lost. Duty keys are
        never re-published after init, so a direct GET is used as a fallback.
        """
        try:
            sensor_keys = list(_KEY_TO_PLACEHOLDER.keys())

            pipe = self._redis.pipeline()
            for key in sensor_keys:
                pipe.get(key)
            results = pipe.execute()

            for key, raw in zip(sensor_keys, results):
                if raw is None:
                    continue
                value = raw.decode() if isinstance(raw, bytes) else str(raw)

                placeholder = _KEY_TO_PLACEHOLDER.get(key)
                if placeholder is None:
                    continue
                if key in _DUTY_KEYS.values():
                    for slot, rkey in _DUTY_KEYS.items():
                        if key == rkey:
                            try:
                                self._current_duty[slot] = int(float(value))
                            except ValueError:
                                pass
                    try:
                        self._values[placeholder] = str(int(float(value)))
                    except ValueError:
                        self._values[placeholder] = value
                elif key in ("sensor:fan_rpm_1", "sensor:fan_rpm_2"):
                    try:
                        self._values[placeholder] = str(int(float(value)))
                    except ValueError:
                        self._values[placeholder] = value
                elif key == "sensor:leak":
                    self._values["LEAK"] = "None" if value == "NORMAL" else "Detected"
                elif key == "sensor:water_level":
                    self._values["WATER_LEVEL"] = _WATER_LEVEL_MAP.get(value, "LOW")
                else:
                    try:
                        self._values[placeholder] = f"{float(value):.1f}"
                    except ValueError:
                        self._values[placeholder] = value

        except Exception as exc:
            log.warning("Failed to load initial Redis values: %s", exc)

        self._update_colors()
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
        # Defensive: buttons should already be disabled in non-manual modes,
        # but guard anyway in case a tap races a mode change.
        if self._current_mode != "manual":
            return
        current = self._current_duty.get(slot, 0)
        dlg = NumpadDialog(current, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_val = dlg.value()
            self._apply_duty(slot, new_val)

    def _apply_duty(self, slot: str, value: int) -> None:
        if self._current_mode != "manual":
            log.warning("Ignoring duty write for %s: mode is %s", slot, self._current_mode)
            return
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
    # Mode gating

    def _load_initial_mode(self) -> None:
        try:
            raw = self._redis.get("control:mode")
            mode = raw.decode() if isinstance(raw, bytes) else (raw or "auto")
        except Exception as exc:
            log.warning("Failed to read control:mode: %s", exc)
            mode = "auto"
        self.on_mode_updated(mode)

    def on_mode_updated(self, mode: str) -> None:
        """Update overlay enable state and gear icon visibility per mode."""
        self._current_mode = mode
        editable = (mode == "manual")
        for btn in self._overlay_btns.values():
            btn.setEnabled(editable)
        self._values["GEAR"] = "⚙" if editable else ""
        self._reload_svg()

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

        # Transform display values
        if key == "sensor:leak":
            self._values["LEAK"] = "None" if value == "NORMAL" else "Detected"
        elif key == "sensor:water_level":
            self._values["WATER_LEVEL"] = _WATER_LEVEL_MAP.get(value, "LOW")
        # Pump/Fan duty, Fan RPM: integer only (no decimal)
        elif key in _DUTY_KEYS.values() or key in ("sensor:fan_rpm_1", "sensor:fan_rpm_2"):
            try:
                self._values[placeholder] = str(int(float(value)))
            except ValueError:
                self._values[placeholder] = value
        else:
            try:
                self._values[placeholder] = f"{float(value):.1f}"
            except ValueError:
                self._values[placeholder] = value

        self._update_colors()
        self._reload_svg()

    # ------------------------------------------------------------------
    # Computed values

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
        v["PH_C"]           = _color_ph(v["PH"])
        v["CONDUCTIVITY_C"] = _color_conductivity(v["CONDUCTIVITY"])

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
