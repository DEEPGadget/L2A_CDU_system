"""Auto-mode controller: 2-point linear fan curve + fixed pump duty.

Stage 1 per docs/auto_control.md. The Settings UI (Local + Web) edits the
following Redis state:
    control:fan_curve   hash  min_temp/max_temp/min_duty/max_duty   (duty x10)
    control:pump_duty   str   integer 0~1000 (= 0.0~100.0 %)

`AutoController` keeps an in-memory copy of those values; `reload()` is called
by the main loop whenever it drains a `control:fan_curve:update` or
`control:pump_duty:update` Pub/Sub message.

Per L1/L2 sync policy (matching the UI's pump/fan duty mirror), Auto uses
`max(outlet_L1, outlet_L2)` as the driving temperature so both fans receive
the same target duty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import redis

from . import redis_keys as K

log = logging.getLogger(__name__)

# Defaults match src/local_ui/pages/settings_page.py _DEFAULT_FAN_CURVE /
# _DEFAULT_PUMP_DUTY so MCG and UI agree even when the hash/string is empty.
_DEFAULT_FAN_CURVE = {
    "min_temp": 25,    # C
    "max_temp": 60,    # C
    "min_duty": 100,   # 0-1000  (= 10.0 % UI)
    "max_duty": 1000,  # 0-1000  (= 100.0 % UI)
}
_DEFAULT_PUMP_DUTY = 600   # 0-1000 (= 60.0 % UI)


@dataclass
class FanCurve:
    min_temp: int
    max_temp: int
    min_duty: int   # 0~1000 scale
    max_duty: int   # 0~1000 scale

    def fan_duty_ui(self, outlet_temp_c: float) -> float:
        """Return fan duty in UI domain (0~100 %) for the given outlet temp."""
        if self.max_temp <= self.min_temp:
            return self.min_duty / 10.0
        if outlet_temp_c <= self.min_temp:
            return self.min_duty / 10.0
        if outlet_temp_c >= self.max_temp:
            return self.max_duty / 10.0
        ratio = (outlet_temp_c - self.min_temp) / (self.max_temp - self.min_temp)
        hr = self.min_duty + ratio * (self.max_duty - self.min_duty)
        return hr / 10.0


class AutoController:
    def __init__(self, r: redis.Redis) -> None:
        self._r = r
        self._fan_curve = FanCurve(**_DEFAULT_FAN_CURVE)
        self._pump_duty_ui = _DEFAULT_PUMP_DUTY / 10.0
        self.reload()

    # ---------- state I/O ----------

    def reload(self) -> bool:
        """Re-read control:fan_curve + control:pump_duty from Redis.
        Returns True if any value changed since the previous reload."""
        prev_fan = self._fan_curve
        prev_pump = self._pump_duty_ui

        try:
            raw = self._r.hgetall(K.CONTROL_FAN_CURVE)
        except Exception as exc:
            log.warning("control:fan_curve hgetall failed: %s", exc)
            raw = {}
        merged = dict(_DEFAULT_FAN_CURVE)
        for key in merged:
            byte_key = key.encode() if isinstance(next(iter(raw), b""), (bytes, bytearray)) else key
            if byte_key in raw:
                try:
                    merged[key] = int(raw[byte_key])
                except (ValueError, TypeError):
                    pass
        self._fan_curve = FanCurve(**merged)

        try:
            raw_pump = self._r.get(K.CONTROL_PUMP_DUTY)
        except Exception as exc:
            log.warning("control:pump_duty get failed: %s", exc)
            raw_pump = None
        if raw_pump is None:
            self._pump_duty_ui = _DEFAULT_PUMP_DUTY / 10.0
        else:
            try:
                self._pump_duty_ui = int(raw_pump) / 10.0
            except (ValueError, TypeError):
                self._pump_duty_ui = _DEFAULT_PUMP_DUTY / 10.0

        changed = (prev_fan != self._fan_curve) or (prev_pump != self._pump_duty_ui)
        if changed:
            log.info("AutoController reloaded: fan_curve=%s pump_duty_ui=%.1f%%",
                     self._fan_curve, self._pump_duty_ui)
        return changed

    # ---------- compute ----------

    def fan_duty_ui(self, outlet_l1_c: float | None, outlet_l2_c: float | None) -> float:
        """Drive both fans off the hotter loop (L1/L2 sync policy)."""
        candidates = [t for t in (outlet_l1_c, outlet_l2_c) if t is not None]
        if not candidates:
            return self._fan_curve.min_duty / 10.0
        return self._fan_curve.fan_duty_ui(max(candidates))

    def pump_duty_ui(self) -> float:
        return self._pump_duty_ui
