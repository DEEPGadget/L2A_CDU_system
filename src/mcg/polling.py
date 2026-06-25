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
  - Input Register 13~16  : Pulse Freq CH1~CH4 (Hz) - real flow sensor
                             frequency output (SIKA VVX15 PushPull, 500
                             pulses/L). 4 sensors on the CH1~4 'T' pulse
                             inputs. Two per loop (parallel branches):
                             Loop1 = CH1+CH2 (IR 13,14),
                             Loop2 = CH3+CH4 (IR 15,16).

Flow rate (PCB.md flow-rate estimation):
  Rev_C introduces real flow sensors on the PCB. There are 4 sensors (one per
  parallel pump branch); each loop has 2, summed to the loop's total flow.
  Each SIKA VVX15 emits a PushPull frequency output (500 pulses/L) wired to the
  CH1~4 'T' pulse inputs and read back as IR 13~16 (Hz). The sensors are powered
  from the CH1~4 'V' pins (12 V, set at boot via CH1~4 duty=100%).
  `_read_flow_lpm()` converts each branch (flow = Hz * 60/500 = Hz * 0.12) and
  sums the two branches per loop. Flow is a *measured* value — never derived
  from pump duty. It returns None on PCB read failure (link down); while None
  the flow keys are simply not published (UI shows no-data, no fabrication).
  Gating is automatic — no manual enable flag.
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

    # 4. Flow rate — real PCB flow sensors only (4× SIKA VVX15 frequency
    #    output on CH1~4 'T' pulse inputs = IR 13~16). Publishes per-loop totals
    #    AND the 4 branch values: Loop1 = CH1+CH2, Loop2 = CH3+CH4. Flow is
    #    measured, NOT derived from pump duty. On read failure (PCB link down)
    #    we publish nothing — UI shows no-data.
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


# ── Real flow sensors (4× SIKA VVX15, frequency output) ──────────────────────
# Config — see docs/PCB.md flow-rate estimation.
# Sensor = VVX15 (Art.No. VVXA1SGAA…): analogue output is 4...20 mA (Pin2) and
# PushPull frequency (Pin4). The PCB ADC reads voltage only (no current
# register), so the 4...20 mA output would need a burden resistor. Instead we
# use the **PushPull frequency output** (500 pulses/L, spec PDF p.5) → CH1~4 'T'
# pulse inputs = IR 13~16 (Hz). The sensors are powered from the CH1~4 'V' pins
# (V = 12 V × duty%, held at 100% by main.py → 12 V).
#   Each loop has 2 parallel-branch sensors; the loop total = their SUM:
#       Loop 1 = CH1 (IR 13) + CH2 (IR 14)
#       Loop 2 = CH3 (IR 15) + CH4 (IR 16)
# - Pulse scaling: 500 pulses/L → flow[L/min] = Hz × 60/500 = Hz × 0.12.
#   (40 LPM ≈ 333 Hz, 2 LPM ≈ 17 Hz — well within the PCB's 0~10 kHz range.)
# Gating is automatic: flow is published whenever the pulse read succeeds (PCB
# link up). When the PCB is unreachable the read returns None → not published →
# UI shows no-data. No manual enable flag.
_FLOW_PULSE_IR_BASE  = 13          # IR 13~16 = pulse freq CH1~4 ('T' inputs)
_FLOW_PULSE_COUNT    = 4
_FLOW_PULSES_PER_L   = 500.0       # SIKA VVX15 pulse rate (spec PDF p.5)
_FLOW_HZ_TO_LPM      = 60.0 / _FLOW_PULSES_PER_L   # = 0.12 (Hz → L/min)


def _read_flow_lpm(pcb: PCB) -> tuple[float, float, float, float] | None:
    """Read the 4 branch flow rates (LPM) from the PCB pulse inputs IR 13~16.

    The 4× SIKA VVX15 sensors emit a PushPull frequency (500 pulses/L) on their
    Pin4, wired to the CH1~4 'T' pulse inputs → IR 13~16 (Hz). They are powered
    from the CH1~4 'V' pins (12 V, set at boot via CH1~4 duty=100% in main.py).

    Returns (b1_1, b1_2, b2_1, b2_2) — loop1 branches (CH1,CH2 = IR 13,14) then
    loop2 branches (CH3,CH4 = IR 15,16). poll_once() sums each loop's two
    branches. Returns None on read failure (PCB link down) → flow not published.
    """
    raw = pcb.read_input_registers(_FLOW_PULSE_IR_BASE, _FLOW_PULSE_COUNT)
    if raw is None or len(raw) < 4:
        return None

    def _branch_lpm(hz: int) -> float:
        # 500 pulses/L → flow[L/min] = Hz × 60/500 = Hz × 0.12. Clamp ≥0.
        return max(0.0, hz * _FLOW_HZ_TO_LPM)

    return (_branch_lpm(raw[0]), _branch_lpm(raw[1]),
            _branch_lpm(raw[2]), _branch_lpm(raw[3]))
