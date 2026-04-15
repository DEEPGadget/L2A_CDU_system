"""Scenario definitions for the fake data simulator.

Each scenario is a dict mapping Redis keys to either:
  - (base, min, max): float tuple — simulator applies slow drift within [min, max]
  - str: fixed string value — written as-is, never drifted

The "warning" and "critical" scenarios inherit from "normal" and override only
the keys that differ. The "no_link" scenario overrides only comm keys and alarms.

Duty keys (pump/fan PWM) are defined only in "normal" as initial values.
The simulator writes them once on startup; after that the UI controls them directly.

Initial duty values reference:
  NVIDIA DGX A100 locks pump at 40 % PWM (steady-state minimum).
  We apply a +20 % safety margin for startup flow assurance.
  - pump: 60 %
  - fan:  15 % (low initial speed; PID takes over after thermal stabilisation)
"""

from __future__ import annotations

from typing import Union

from src import thresholds as T

# Type alias: float drift tuple or fixed string
_Value = Union[tuple[float, float, float], str]

# Base sensor values used as the foundation for all scenarios.
_NORMAL_BASE: dict[str, _Value] = {
    "sensor:coolant_temp_inlet_1":  (30.0, T.INLET_TEMP_NORMAL_LO,  T.INLET_TEMP_NORMAL_HI),
    "sensor:coolant_temp_inlet_2":  (29.5, T.INLET_TEMP_NORMAL_LO,  T.INLET_TEMP_NORMAL_HI),
    "sensor:coolant_temp_outlet_1": (44.0, T.OUTLET_TEMP_WARN_LO,   T.OUTLET_TEMP_NORMAL_HI),
    "sensor:coolant_temp_outlet_2": (43.5, T.OUTLET_TEMP_WARN_LO,   T.OUTLET_TEMP_NORMAL_HI),
    "sensor:flow_rate_1":           (5.2,  4.5,  6.0),
    "sensor:flow_rate_2":           (5.0,  4.5,  6.0),
    "sensor:water_level_high":      "1",
    "sensor:water_level_low":       "1",
    "sensor:ph":                    (7.2,  6.8,  7.6),
    "sensor:conductivity":          (150.0, 100.0, 200.0),
    "sensor:leak":                  "NORMAL",
    "sensor:ambient_temp":          (25.0, 18.0,                    T.AMBIENT_TEMP_WARN_HI),
    "sensor:ambient_humidity":      (45.0, T.AMBIENT_HUM_NORMAL_LO,  T.AMBIENT_HUM_WARN_HI),
    "sensor:pressure":              (1.2,  0.8,  1.8),
    # Duty: initialised once by simulator, never overwritten afterwards
    "sensor:pump_pwm_duty_1":       "60",
    "sensor:pump_pwm_duty_2":       "60",
    "sensor:fan_pwm_duty_1":        "15",
    "sensor:fan_pwm_duty_2":        "15",
    "comm:status":                  "ok",
    "comm:consecutive_failures":    "0",
}

_NORMAL_ALARMS: list[str] = []

_WARNING_OVERRIDES: dict[str, _Value] = {
    "sensor:coolant_temp_inlet_1":  (43.0, T.INLET_TEMP_NORMAL_HI + 1, T.INLET_TEMP_CRIT_HI),
    "sensor:coolant_temp_outlet_1": (62.0, T.OUTLET_TEMP_NORMAL_HI,    T.OUTLET_TEMP_CRIT_HI),
    "sensor:water_level_high":      "0",   # MIDDLE level
    "sensor:water_level_low":       "1",
    "sensor:ambient_humidity":      (72.0, T.AMBIENT_HUM_WARN_HI, T.AMBIENT_HUM_CRIT_HI),
    "comm:status":                  "ok",
    "comm:consecutive_failures":    "0",
}

_WARNING_ALARMS: list[str] = [
    "alarm:coolant_temp_warning",
    "alarm:water_level_warning",
    "alarm:ambient_humidity_warning",
]

_CRITICAL_OVERRIDES: dict[str, _Value] = {
    "sensor:coolant_temp_inlet_1":  (48.0, T.INLET_TEMP_CRIT_HI,   T.INLET_TEMP_CRIT_HI  + 7.0),
    "sensor:coolant_temp_outlet_1": (67.0, T.OUTLET_TEMP_CRIT_HI,  T.OUTLET_TEMP_CRIT_HI + 7.0),
    "sensor:leak":                  "LEAKED",
    "sensor:ambient_temp":          (47.0, T.AMBIENT_TEMP_CRIT_HI, T.AMBIENT_TEMP_CRIT_HI + 10.0),
    "comm:status":                  "timeout",
    "comm:consecutive_failures":    "3",
}

_CRITICAL_ALARMS: list[str] = [
    "alarm:coolant_temp_critical",
    "alarm:leak_detected",
    "alarm:ambient_temp_critical",
    "alarm:comm_timeout",
]

_NO_LINK_OVERRIDES: dict[str, _Value] = {
    # Sensor values keep normal base (stale but present)
    "comm:status":               "disconnected",
    "comm:consecutive_failures": "10",
}

_NO_LINK_ALARMS: list[str] = [
    "alarm:comm_disconnected",
]


def _merge(base: dict[str, _Value], overrides: dict[str, _Value]) -> dict[str, _Value]:
    merged = dict(base)
    merged.update(overrides)
    return merged


# Public scenario registry
# Each entry: {"sensors": {key: value}, "alarms": [alarm_key, ...]}
SCENARIOS: dict[str, dict] = {
    "normal": {
        "sensors": dict(_NORMAL_BASE),
        "alarms":  list(_NORMAL_ALARMS),
    },
    "warning": {
        "sensors": _merge(_NORMAL_BASE, _WARNING_OVERRIDES),
        "alarms":  list(_WARNING_ALARMS),
    },
    "critical": {
        "sensors": _merge(_NORMAL_BASE, _CRITICAL_OVERRIDES),
        "alarms":  list(_CRITICAL_ALARMS),
    },
    "no_link": {
        "sensors": _merge(_NORMAL_BASE, _NO_LINK_OVERRIDES),
        "alarms":  list(_NO_LINK_ALARMS),
    },
}

DUTY_KEYS: frozenset[str] = frozenset({
    "sensor:pump_pwm_duty_1",
    "sensor:pump_pwm_duty_2",
    "sensor:fan_pwm_duty_1",
    "sensor:fan_pwm_duty_2",
})
