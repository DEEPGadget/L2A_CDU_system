"""Demo data seeder — writes STABLE FAKE sensor values into Redis so the Local
UI, Web UI, and Prometheus exporter display realistic data with NO PCB.

Used on demo SDs IN PLACE OF cdu-mcg. The real cdu-mcg MUST be masked/stopped
(see scripts/setup-demo.sh): when no PCB responds it sets comm:status=disconnected
and DELETES the sensed keys, which would wipe these values.

Values are written in the exact format polling.py / the UIs expect (so every
key/channel is interpreted correctly), with a small jitter so charts look alive
but stable. Each SET is mirrored with a PUBLISH on a channel named after the key
(the project convention) so both UIs update live.

Run: python -m src.demo.seeder
"""
from __future__ import annotations

import random
import signal
import time

import redis

from src.mcg import redis_keys as K

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

CYCLE_SECONDS = 2.0


def _f1(v: float) -> str:
    """One-decimal float string — temps, flow, ambient (matches polling.py)."""
    return f"{v:.1f}"


def _i(v: float) -> str:
    """Integer string — fan RPM, PWM duty (UI %)."""
    return str(int(round(v)))


# Jittered numeric values: (key, base, jitter, formatter).
# Base values sit near the certification operating point (inlet ~30, ΔT ~13,
# ~70 LPM/loop). Branch flows are summed into the loop totals each cycle.
_NUMERIC = [
    (K.SENSOR_COOLANT_TEMP_INLET_1,  30.0, 0.2, _f1),
    (K.SENSOR_COOLANT_TEMP_OUTLET_1, 44.0, 0.2, _f1),
    (K.SENSOR_COOLANT_TEMP_INLET_2,  31.0, 0.2, _f1),
    (K.SENSOR_COOLANT_TEMP_OUTLET_2, 43.0, 0.2, _f1),
    (K.SENSOR_FLOW_RATE_1_1, 35.0, 0.3, _f1),
    (K.SENSOR_FLOW_RATE_1_2, 35.0, 0.3, _f1),
    (K.SENSOR_FLOW_RATE_2_1, 34.0, 0.3, _f1),
    (K.SENSOR_FLOW_RATE_2_2, 34.0, 0.3, _f1),
    (K.SENSOR_FAN_RPM_1, 3000, 20, _i),
    (K.SENSOR_FAN_RPM_2, 2950, 20, _i),
    (K.SENSOR_AMBIENT_TEMP, 25.0, 0.1, _f1),
    (K.SENSOR_AMBIENT_HUMIDITY, 45.0, 0.3, _f1),
]

# Fixed (no jitter) values.
_FIXED = [
    (K.SENSOR_PUMP_PWM_DUTY_1, "78"),   # UI % — cert default pump duty
    (K.SENSOR_PUMP_PWM_DUTY_2, "78"),
    (K.SENSOR_FAN_PWM_DUTY_1, "100"),   # UI % — cert default fan duty
    (K.SENSOR_FAN_PWM_DUTY_2, "100"),
    (K.SENSOR_WATER_LEVEL, "2"),        # 2 = HIGH (normal)
    (K.SENSOR_LEAK, "NORMAL"),
    ("sensor:din_raw", "4"),
]

_running = True


def _stop(*_args) -> None:
    global _running
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

    # Demo inherits cert's Manual lock — make sure the mode reads Manual.
    if r.get(K.CONTROL_MODE) is None:
        r.set(K.CONTROL_MODE, "manual")
        r.publish(K.CONTROL_MODE, "manual")

    while _running:
        pipe = r.pipeline()
        branch = {}
        for key, base, jit, fmt in _NUMERIC:
            v = base + random.uniform(-jit, jit)
            branch[key] = v
            s = fmt(v)
            pipe.set(key, s)
            pipe.publish(key, s)

        # Loop totals = sum of the two branches (keep them consistent).
        t1 = branch[K.SENSOR_FLOW_RATE_1_1] + branch[K.SENSOR_FLOW_RATE_1_2]
        t2 = branch[K.SENSOR_FLOW_RATE_2_1] + branch[K.SENSOR_FLOW_RATE_2_2]
        for tk, tv in ((K.SENSOR_FLOW_RATE_1, t1), (K.SENSOR_FLOW_RATE_2, t2)):
            s = _f1(tv)
            pipe.set(tk, s)
            pipe.publish(tk, s)

        for key, s in _FIXED:
            pipe.set(key, s)
            pipe.publish(key, s)

        # Keep the link "connected" every cycle so the UIs never go no-data.
        pipe.set(K.COMM_STATUS, "ok")
        pipe.publish(K.COMM_STATUS, "ok")
        pipe.set(K.COMM_CONSECUTIVE_FAILURES, "0")

        pipe.execute()
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    main()
