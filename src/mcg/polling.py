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
  - Input Register 32~33  : ADC Voltage CH1/CH2 (0.01 V unit) - real flow
                             sensor analogue output (SIKA VVX, 0.5~3.5 V).
                             L1 = CH1 (IR 32), L2 = CH2 (IR 33).

Flow rate (PCB.md "유량 추정"):
  Rev_C introduces real flow sensors on the PCB (one per loop at the
  manifold confluence). The sensor (SIKA VVX20) emits a 0.5~3.5 V analogue
  signal proportional to flow; it is wired to the PCB ADC voltage inputs
  AIN1/AIN2 and read back as IR 32/33 (0.01 V). `_read_flow_lpm()` reads
  those registers and applies the model-specific linear scaling. Flow is a
  *measured* value — it is never derived from pump duty. It returns
  (None, None) until `_FLOW_SENSOR_ENABLED` is flipped on at bring-up; while
  it returns None the flow keys are simply not published (no fabricated
  estimate — the UI shows no-data).
"""

from __future__ import annotations

import logging

import redis

from . import redis_keys as K
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

    # 4. Flow rate per loop — real PCB flow sensor only (SIKA VVX, analogue
    #    voltage on IR 32/33). Flow is a measured value; it is NOT derived from
    #    pump duty. When the sensor is unavailable (_FLOW_SENSOR_ENABLED off, or
    #    read failure) we publish nothing — the key keeps its last value / the
    #    UI shows no-data rather than a fabricated estimate.
    f1_real, f2_real = _read_flow_lpm(pcb)
    if f1_real is not None and f2_real is not None:
        _publish(pipe, K.SENSOR_FLOW_RATE_1, f"{f1_real:.1f}")
        _publish(pipe, K.SENSOR_FLOW_RATE_2, f"{f2_real:.1f}")

    pipe.execute()
    return True


# ── Real flow sensor (SIKA VVX, analogue voltage output) ─────────────────────
# Config — see docs/PCB.md "유량 추정".
# - Sensor outputs an analogue voltage proportional to flow (0.5~3.5 V),
#   wired to the PCB ADC voltage inputs AIN1 (L1) / AIN2 (L2) and read back
#   as IR 32 / IR 33 (0.01 V unit, e.g. 350 = 3.50 V).
# - Linear scaling is model-specific (0.5 V = min flow, 3.5 V = max flow):
#       VVX20 (cert):  0.5 V→5 LPM,  3.5 V→80 LPM  ->  flow = 25.0  * V - 7.5
#       VVX15 (prod):  0.5 V→2 LPM,  3.5 V→40 LPM  ->  flow = 12.667 * V - 4.333
# - Flip _FLOW_SENSOR_ENABLED = True once the physical sensor is installed
#   and the ADC channels are confirmed at PCB bring-up; set _FLOW_MODEL to
#   match the fitted sensor.
_FLOW_SENSOR_ENABLED = False
_FLOW_VOLT_IR_BASE   = 32          # IR 32 = ADC voltage CH1 (L1), IR 33 = CH2 (L2)
_FLOW_VOLT_COUNT     = 2
_FLOW_MODEL          = "VVX20"     # "VVX20" (cert) | "VVX15" (production)
_FLOW_SCALE          = {           # (slope, intercept) for flow_lpm = slope*V + intercept
    "VVX20": (25.0, -7.5),
    "VVX15": (12.667, -4.333),
}


def _read_flow_lpm(pcb: PCB) -> tuple[float | None, float | None]:
    """Read real per-loop flow rate (L1, L2) in LPM from the PCB ADC voltage input.

    Returns (None, None) until _FLOW_SENSOR_ENABLED is flipped on (sensor
    installed + _FLOW_MODEL confirmed). The fallback in poll_once() then keeps
    the duty-derived estimate.
    """
    if not _FLOW_SENSOR_ENABLED:
        return (None, None)
    raw = pcb.read_input_registers(_FLOW_VOLT_IR_BASE, _FLOW_VOLT_COUNT)
    if raw is None:
        return (None, None)
    slope, intercept = _FLOW_SCALE[_FLOW_MODEL]
    v1 = raw[0] / 100.0            # IR unit is 0.01 V
    v2 = raw[1] / 100.0
    # Clamp to 0: below the 0.5 V floor the linear fit goes negative (no flow).
    f1 = max(0.0, slope * v1 + intercept)
    f2 = max(0.0, slope * v2 + intercept)
    return (f1, f2)
