"""PCB polling: read sensors over Modbus, publish to Redis.

Called once per main-loop cycle. On any read failure the function returns
False so the caller can update comm:status.

Register map (docs/PCB.md "Modbus Registers"):
  - Input Register 28~31  : NTC Temp (0.1 C unit) - inlet L1, inlet L2,
                             outlet L1, outlet L2
  - Input Register 20, 21 : Pulse Freq CH8, CH9 (Hz) - fan RPM feedback
                             (RPM = Hz * 30, 2 pulses/revolution)
  - Input Register 25     : DIN Status (bit0~5) - water level / leak inputs
                             (bit assignment TBD until PCB bring-up;
                             currently published as raw integer only)

Flow estimation (PCB.md "Flow estimation"):
  sensor:flow_rate_1/_2 and sensor:total_flow are derived in this same cycle
  from the latest pump_pwm_duty values held in Redis. Fake-mode simulator
  uses the same formula in src/fake_data/simulator.py so both modes are
  byte-identical from the UI's perspective.
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
_NTC_REDIS_KEYS = (
    K.SENSOR_COOLANT_TEMP_INLET_1,
    K.SENSOR_COOLANT_TEMP_INLET_2,
    K.SENSOR_COOLANT_TEMP_OUTLET_1,
    K.SENSOR_COOLANT_TEMP_OUTLET_2,
)

_PULSE_BASE  = 20         # Pulse CH8 (= IR 20). CH9 = IR 21.
_PULSE_COUNT = 2
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
        # IR value is tenths of degC (e.g. 253 -> 25.3)
        celsius = raw / 10.0
        _publish(pipe, key, f"{celsius:.1f}")

    # 2. Fan RPM (best-effort; do not abort if it fails)
    pulse = pcb.read_input_registers(_PULSE_BASE, _PULSE_COUNT)
    if pulse is not None:
        for hz, key in zip(pulse, _FAN_RPM_REDIS_KEYS):
            rpm = hz * 30   # 2 pulses/revolution
            _publish(pipe, key, str(rpm))

    # 3. DIN raw (water level / leak bit mapping TBD - publish raw integer)
    din = pcb.read_input_registers(_DIN_BASE, _DIN_COUNT)
    if din is not None:
        # TODO(REV_C bring-up): decode water_level and leak bits once PCB
        # wiring is confirmed; for now keep the raw value reachable for ops.
        _publish(pipe, "sensor:din_raw", str(din[0]))

    # 4. Derive flow from current pump duty held in Redis (UI domain 0~100 %)
    d1 = _to_float(r.get(K.SENSOR_PUMP_PWM_DUTY_1))
    d2 = _to_float(r.get(K.SENSOR_PUMP_PWM_DUTY_2))
    f1 = loop_flow_lpm(d1)
    f2 = loop_flow_lpm(d2)
    _publish(pipe, K.SENSOR_FLOW_RATE_1, f"{f1:.1f}")
    _publish(pipe, K.SENSOR_FLOW_RATE_2, f"{f2:.1f}")
    _publish(pipe, K.SENSOR_TOTAL_FLOW,  f"{f1 + f2:.1f}")

    pipe.execute()
    return True


def _to_float(raw) -> float:
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0
