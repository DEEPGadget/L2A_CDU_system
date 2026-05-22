"""PCB polling: read sensors over Modbus, publish to Redis.

Called once per main-loop cycle. On any read failure the function returns
False so the caller can update comm:status.

Register map (docs/PCB.md "Modbus Registers"):
  - Input Register 28~31  : NTC Temp (0.1 C unit, **signed int16**) ordered as
                             T1 inlet_L1, T2 outlet_L1, T3 outlet_L2,
                             T4 inlet_L2 -- per board silkscreen.
                             Open circuit returns ~-40.4 C (raw 0xFE6C).
  - Input Register 17~20  : Pulse Freq CH5~CH8 (Hz) - fan RPM feedback
                             (RPM = Hz * 30, 2 pulses/revolution).
                             L1 = CH5,6 (IR 17,18), L2 = CH7,8 (IR 19,20).
                             MCG publishes the per-loop 2ch **average** to
                             sensor:fan_rpm_1 / _2 (UI shows the average).
  - Input Register 25     : DIN Status (bit0~5) - water level / leak inputs
                             (bit assignment TBD until PCB bring-up;
                             currently published as raw integer only)

Flow estimation (PCB.md "Flow estimation"):
  Rev_C introduces real flow sensors on the PCB (one per loop at the
  manifold confluence). `_read_flow_lpm()` is the hook for that read; it
  returns (None, None) until the sensor channel and conversion factor are
  confirmed. While the hook returns None, we fall back to the derived
  formula (`70 * ui_duty / 100` LPM per loop — parallel pump pair) so the
  UI and fake simulator stay byte-identical with the pre-sensor contract.
"""

from __future__ import annotations

import logging

import redis

from . import redis_keys as K
from .duty_mapper import loop_flow_lpm
from .modbus_client import PCB

log = logging.getLogger(__name__)

# Register layout
_NTC_BASE  = 28
_NTC_COUNT = 4
# IR 28~31 in physical T1/T2/T3/T4 silkscreen order:
#   T1 = inlet  L1   (IR 28)
#   T2 = outlet L1   (IR 29)
#   T3 = outlet L2   (IR 30)
#   T4 = inlet  L2   (IR 31)
_NTC_REDIS_KEYS = (
    K.SENSOR_COOLANT_TEMP_INLET_1,   # T1
    K.SENSOR_COOLANT_TEMP_OUTLET_1,  # T2
    K.SENSOR_COOLANT_TEMP_OUTLET_2,  # T3
    K.SENSOR_COOLANT_TEMP_INLET_2,   # T4
)


def _signed16(u: int) -> int:
    """Decode an unsigned 16-bit Modbus register as signed (two's complement).
    NTC range -40 ~ 85 C means raw values can be slightly negative
    (e.g. open circuit returns ~0xFE6C = -404 -> -40.4 C)."""
    return u - 0x10000 if u >= 0x8000 else u

# Pulse CH N -> IR (12 + N). L2A Rev_C uses fan CH 5~8 -> IR 17~20 (4 ch).
# Read all 4 in one transaction; per-loop 2-ch average is published to the
# 2 RPM keys.
_PULSE_BASE  = 17
_PULSE_COUNT = 4
_FAN_RPM_REDIS_KEYS = (K.SENSOR_FAN_RPM_1, K.SENSOR_FAN_RPM_2)

_DIN_BASE  = 25
_DIN_COUNT = 1


def _publish(pipe: "redis.client.Pipeline", key: str, value: str) -> None:
    pipe.set(key, value)
    pipe.publish(key, value)


def poll_once(pcb: PCB, r: redis.Redis) -> bool:
    """Single polling pass. Returns True if at least the NTC read succeeded."""
    pipe = r.pipeline()

    # 1. NTC temperatures - canonical "we are alive" read.
    ntc = pcb.read_input_registers(_NTC_BASE, _NTC_COUNT)
    if ntc is None:
        return False
    for raw, key in zip(ntc, _NTC_REDIS_KEYS):
        # IR value is tenths of degC, signed int16 (e.g. 253 -> 25.3,
        # 0xFE6C = -404 -> -40.4 for open-circuit / unconnected NTC)
        celsius = _signed16(raw) / 10.0
        _publish(pipe, key, f"{celsius:.1f}")

    # 2. Fan RPM (best-effort; do not abort if it fails).
    #    4 channels read, per-loop 2ch average -> 2 Redis keys (UI shows avg).
    pulse = pcb.read_input_registers(_PULSE_BASE, _PULSE_COUNT)
    if pulse is not None:
        # pulse[0:2] = L1 (CH5,6), pulse[2:4] = L2 (CH7,8)
        rpm_l1 = round(sum(pulse[0:2]) / 2 * 30)  # 2 pulses/revolution
        rpm_l2 = round(sum(pulse[2:4]) / 2 * 30)
        _publish(pipe, _FAN_RPM_REDIS_KEYS[0], str(rpm_l1))
        _publish(pipe, _FAN_RPM_REDIS_KEYS[1], str(rpm_l2))

    # 3. DIN raw (water level / leak bit mapping TBD - publish raw integer)
    din = pcb.read_input_registers(_DIN_BASE, _DIN_COUNT)
    if din is not None:
        # TODO(REV_C bring-up): decode water_level and leak bits once PCB
        # wiring is confirmed; for now keep the raw value reachable for ops.
        _publish(pipe, "sensor:din_raw", str(din[0]))

    # 4. Flow rate per loop. Prefer the real PCB sensor (Rev_C+) once it is
    #    wired; until then, fall back to the duty-derived estimate.
    f1_real, f2_real = _read_flow_lpm(pcb)
    if f1_real is None or f2_real is None:
        d1 = _to_float(r.get(K.SENSOR_PUMP_PWM_DUTY_1))
        d2 = _to_float(r.get(K.SENSOR_PUMP_PWM_DUTY_2))
        f1 = loop_flow_lpm(d1) if f1_real is None else f1_real
        f2 = loop_flow_lpm(d2) if f2_real is None else f2_real
    else:
        f1, f2 = f1_real, f2_real
    _publish(pipe, K.SENSOR_FLOW_RATE_1, f"{f1:.1f}")
    _publish(pipe, K.SENSOR_FLOW_RATE_2, f"{f2:.1f}")

    pipe.execute()
    return True


# ── Real flow sensor (SIKA VVX20, Frequency output) ──────────────────────────
# Config — see docs/PCB.md "실 센서 후보: SIKA VVX".
# - Model: VVX20 (DN20, 4..80 L/min, 200 pulses/L).
# - Sensor outputs a square-wave frequency proportional to flow:
#       flow_lpm = Hz * 60 / 200 = Hz * 0.3
# - Wired to PCB pulse-input CH1 (L1) and CH2 (L2) → IR 13 and IR 14 (Hz).
# - Flip _FLOW_SENSOR_ENABLED = True once the physical sensor is installed
#   and the pulse channels are confirmed at PCB bring-up.
_FLOW_SENSOR_ENABLED = False
_FLOW_PULSE_IR_BASE  = 13          # IR 13 = CH1 (L1), IR 14 = CH2 (L2)
_FLOW_PULSE_COUNT    = 2
_PULSES_PER_LITER    = 200         # VVX20


def _read_flow_lpm(pcb: PCB) -> tuple[float | None, float | None]:
    """Read real per-loop flow rate (L1, L2) in LPM from the PCB pulse input.

    Returns (None, None) until _FLOW_SENSOR_ENABLED is flipped on (sensor
    installed + model-specific _PULSES_PER_LITER confirmed). The fallback in
    poll_once() then keeps the duty-derived estimate.
    """
    if not _FLOW_SENSOR_ENABLED:
        return (None, None)
    hz = pcb.read_input_registers(_FLOW_PULSE_IR_BASE, _FLOW_PULSE_COUNT)
    if hz is None:
        return (None, None)
    scale = 60.0 / _PULSES_PER_LITER
    return (hz[0] * scale, hz[1] * scale)


def _to_float(raw) -> float:
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0
