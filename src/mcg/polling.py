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
  - Input Register 32~35  : ADC Voltage CH1~4 (0.01 V unit) - real flow
                             sensor analogue output (SIKA VVX15, 0.5~3.5 V),
                             4 sensors on AIN1~4. Two per loop (parallel
                             branches): Loop1 = AIN1+AIN2 (IR 32,33),
                             Loop2 = AIN3+AIN4 (IR 34,35).

Flow rate (PCB.md flow-rate estimation):
  Rev_C introduces real flow sensors on the PCB. There are 4 sensors (one per
  parallel pump branch); each loop has 2, summed to the loop's total flow.
  Each SIKA VVX15 emits a 0.5~3.5 V analogue signal proportional to flow,
  wired to ADC inputs AIN1~4 and read back as IR 32~35 (0.01 V).
  `_read_flow_lpm()` converts each branch with the model-specific linear
  scaling and sums the two branches per loop. Flow is a *measured* value —
  never derived from pump duty. It returns (None, None) until
  `_FLOW_SENSOR_ENABLED` is flipped on at bring-up; while it returns None the
  flow keys are simply not published (the UI shows no-data, no fabrication).
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

    # 4. Flow rate — real PCB flow sensors only (4× SIKA VVX15 on AIN1~4 =
    #    IR 32~35). Publishes per-loop totals AND the 4 branch values:
    #    Loop1 = AIN1+AIN2, Loop2 = AIN3+AIN4. Flow is measured, NOT derived
    #    from pump duty. When sensors are unavailable (_FLOW_SENSOR_ENABLED off
    #    or read failure) we publish nothing — UI shows no-data.
    branches = _read_flow_lpm(pcb)
    if branches is not None:
        b11, b12, b21, b22 = branches
        for (total_key, (b1_key, b2_key)), b1, b2 in (
            (K.FLOW_LOOPS[0], b11, b12),
            (K.FLOW_LOOPS[1], b21, b22),
        ):
            _publish(pipe, b1_key, f"{b1:.1f}")
            _publish(pipe, b2_key, f"{b2:.1f}")
            _publish(pipe, total_key, f"{b1 + b2:.1f}")

    pipe.execute()
    return True


# ── Real flow sensors (4× SIKA VVX15, output version ③) ──────────────────────
# Config — see docs/PCB.md flow-rate estimation.
# Sensor = VVX15, output version ③ "Analogue 0...10 V or 4...20 mA + frequency"
# (spec PDF p.5); temperature output: none. We use the **0...10 V** analogue
# output → PCB ADC voltage inputs AIN1~4 = IR 32~35 (0.01 V unit, 1000 = 10.00 V).
#   (PCB ADC is 0~12 V, so 0...10 V is directly compatible — no burden resistor;
#    4...20 mA would need one. The push-pull frequency output is unused — pulse
#    channels are taken by the fan tachs.)
#   Each loop has 2 parallel-branch sensors; the loop total = their SUM:
#       Loop 1 = AIN1 (IR 32) + AIN2 (IR 33)
#       Loop 2 = AIN3 (IR 34) + AIN4 (IR 35)
# - 0...10 V linear scaling: 0 V = 0 LPM, 10 V = 40 LPM  ->  flow = 4.0 * V.
#   (4...20 mA alt: flow = 2.5*(I-4). VVX20 = 0...80 LPM @ 0...10 V → flow = 8*V.)
# - Flip _FLOW_SENSOR_ENABLED = True once the sensors are installed and the ADC
#   channels are confirmed at PCB bring-up.
_FLOW_SENSOR_ENABLED = False
_FLOW_VOLT_IR_BASE   = 32          # IR 32~35 = ADC voltage CH1~4 = AIN1~4
_FLOW_VOLT_COUNT     = 4
_FLOW_MODEL          = "VVX15"     # unified (cert + production)
# (slope, intercept) for flow_lpm = slope*V + intercept, 0...10 V analogue output.
_FLOW_SCALE          = {
    "VVX15": (4.0, 0.0),           # 0 V=0, 10 V=40 LPM
    "VVX20": (8.0, 0.0),           # 0 V=0, 10 V=80 LPM (reference)
}


def _read_flow_lpm(pcb: PCB) -> tuple[float, float, float, float] | None:
    """Read the 4 branch flow rates (LPM) from the PCB ADC inputs IR 32~35.

    Returns (b1_1, b1_2, b2_1, b2_2) — loop1 branches then loop2 branches
    (AIN1, AIN2, AIN3, AIN4). poll_once() sums each loop's two branches.
    Returns None until _FLOW_SENSOR_ENABLED is on, or on read failure.
    """
    if not _FLOW_SENSOR_ENABLED:
        return None
    raw = pcb.read_input_registers(_FLOW_VOLT_IR_BASE, _FLOW_VOLT_COUNT)
    if raw is None or len(raw) < 4:
        return None
    slope, intercept = _FLOW_SCALE[_FLOW_MODEL]

    def _branch_lpm(reg: int) -> float:
        # IR unit is 0.01 V; 0...10 V analogue output → flow = slope*V. Clamp ≥0.
        return max(0.0, slope * (reg / 100.0) + intercept)

    return (_branch_lpm(raw[0]), _branch_lpm(raw[1]),
            _branch_lpm(raw[2]), _branch_lpm(raw[3]))
