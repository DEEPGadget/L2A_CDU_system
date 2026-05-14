"""Fake data simulator — standalone script.

Reads config/config.yaml. Exits with code 1 if mode != 'fake',
which causes systemd (via Restart=on-failure) to skip startup.

Usage:
    python simulator.py --scenario normal --interval 2

Scenarios: normal | warning | critical | no_link
Interval:  seconds between sensor value updates (default 2)

Behaviour:
  - Duty keys (pump/fan PWM) are written ONCE on startup, then never touched.
    The UI writes them directly after the user applies a change.
  - Float sensor values drift slowly by ±DRIFT_STEP per update cycle,
    bouncing within the (min, max) bounds defined in scenarios.py.
  - String (fixed) sensor values are written every cycle unchanged.
  - Alarm keys: SET if in scenario alarms list, DEL otherwise.
  - comm keys: written every cycle unchanged.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
import os

import redis

# Allow running directly: python src/fake_data/simulator.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config import get_config
from src.fake_data.scenarios import DUTY_KEYS, SCENARIOS
from src import thresholds as T

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [simulator] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

DRIFT_STEP = 0.2   # °C (or matching unit) per update cycle
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0


class FakeDataSimulator:
    def __init__(self, scenario: str, interval: float) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario}'. "
                f"Valid options: {', '.join(SCENARIOS)}"
            )
        self._scenario = scenario
        self._interval = interval
        self._running = False
        self._redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

        # Current drift state: key → current float value
        self._current: dict[str, float] = {}
        # Drift direction per key: +1 or -1
        self._direction: dict[str, float] = {}
        # Current string sensor values (water level, leak, comm, etc.)
        self._str_current: dict[str, str] = {}

        self._init_drift_state()

    # ------------------------------------------------------------------
    # Setup

    def _init_drift_state(self) -> None:
        sensors = SCENARIOS[self._scenario]["sensors"]
        for key, value in sensors.items():
            if isinstance(value, tuple):
                base, low, high = value
                self._current[key] = base
                self._direction[key] = 1.0
            else:
                self._str_current[key] = str(value)

    # ------------------------------------------------------------------
    # Public

    def start(self) -> None:
        log.info("Simulator starting — scenario=%s interval=%ss", self._scenario, self._interval)
        self._running = True
        self._initialize_duty_keys()
        self._loop()

    def stop(self) -> None:
        log.info("Simulator stopping.")
        self._running = False

    # ------------------------------------------------------------------
    # Main loop

    def _loop(self) -> None:
        while self._running:
            self._update_sensors()
            self._update_alarms()
            time.sleep(self._interval)

    # ------------------------------------------------------------------
    # Sensor update

    def _initialize_duty_keys(self) -> None:
        sensors = SCENARIOS[self._scenario]["sensors"]
        pipe = self._redis.pipeline()
        for key in DUTY_KEYS:
            if key in sensors:
                value = sensors[key]
                pipe.set(key, str(value))
                pipe.publish(key, str(value))
        pipe.execute()
        log.info("Duty keys initialised: %s", {k: sensors[k] for k in DUTY_KEYS if k in sensors})

    def _update_sensors(self) -> None:
        sensors = SCENARIOS[self._scenario]["sensors"]
        pipe = self._redis.pipeline()
        for key, spec in sensors.items():
            if key in DUTY_KEYS:
                continue  # never overwrite duty keys after init

            if isinstance(spec, tuple):
                new_val = self._drift(key, spec)
                str_val = f"{new_val:.2f}"
            else:
                str_val = spec
                self._str_current[key] = str_val

            pipe.set(key, str_val)
            pipe.publish(key, str_val)

        # Derived: Total Flow = flow_L1 + flow_L2 (MCG 측과 동일 정의)
        f1 = self._current.get("sensor:flow_rate_1")
        f2 = self._current.get("sensor:flow_rate_2")
        if f1 is not None and f2 is not None:
            total_str = f"{(f1 + f2):.2f}"
            pipe.set("sensor:total_flow", total_str)
            pipe.publish("sensor:total_flow", total_str)

        pipe.execute()

    def _drift(self, key: str, spec: tuple[float, float, float]) -> float:
        _, low, high = spec
        current = self._current[key]
        direction = self._direction[key]

        new_val = current + direction * DRIFT_STEP

        if new_val >= high:
            new_val = high
            self._direction[key] = -1.0
        elif new_val <= low:
            new_val = low
            self._direction[key] = 1.0

        self._current[key] = new_val
        return new_val

    # ------------------------------------------------------------------
    # Alarm evaluation — mirrors AEM threshold logic in real mode

    def _evaluate_thresholds(self) -> set[str]:
        """Derive active alarm keys from current sensor values."""
        active: set[str] = set()

        def fval(key: str) -> float | None:
            return self._current.get(key)

        def sval(key: str) -> str:
            return self._str_current.get(key, "")

        # Coolant temperature — per loop (inlet + outlet combined into one loop alarm)
        for i in (1, 2):
            inlet  = fval(f"sensor:coolant_temp_inlet_{i}")
            outlet = fval(f"sensor:coolant_temp_outlet_{i}")

            if inlet is not None:
                if inlet > T.INLET_TEMP_CRIT_HI or inlet < T.INLET_TEMP_CRIT_LO:
                    active.add(f"alarm:coolant_temp_l{i}_critical")
                elif inlet > T.INLET_TEMP_NORMAL_HI or inlet < T.INLET_TEMP_NORMAL_LO:
                    active.add(f"alarm:coolant_temp_l{i}_warning")

            if outlet is not None:
                if outlet > T.OUTLET_TEMP_CRIT_HI or outlet < T.OUTLET_TEMP_CRIT_LO:
                    active.add(f"alarm:coolant_temp_l{i}_critical")
                elif outlet > T.OUTLET_TEMP_NORMAL_HI or outlet < T.OUTLET_TEMP_WARN_LO:
                    active.add(f"alarm:coolant_temp_l{i}_warning")


        # Water level
        wl = sval("sensor:water_level")
        if wl == "0":
            active.add("alarm:water_level_critical")
        elif wl == "1":
            active.add("alarm:water_level_warning")

        # Leak
        if sval("sensor:leak") == "LEAKED":
            active.add("alarm:leak_detected")

        # Ambient temperature
        v = fval("sensor:ambient_temp")
        if v is not None:
            if v > T.AMBIENT_TEMP_CRIT_HI:
                active.add("alarm:ambient_temp_critical")
            elif v > T.AMBIENT_TEMP_WARN_HI:
                active.add("alarm:ambient_temp_warning")

        # Ambient humidity
        v = fval("sensor:ambient_humidity")
        if v is not None:
            if v > T.AMBIENT_HUM_CRIT_HI or v < T.AMBIENT_HUM_CRIT_LO:
                active.add("alarm:ambient_humidity_critical")
            elif v > T.AMBIENT_HUM_WARN_HI:
                active.add("alarm:ambient_humidity_warning")

        # pH
        v = fval("sensor:ph")
        if v is not None and v < T.PH_WARN_LO:
            active.add("alarm:ph_warning")

        # Conductivity
        v = fval("sensor:conductivity")
        if v is not None and v < T.CONDUCTIVITY_WARN_LO:
            active.add("alarm:conductivity_warning")

        # Communication
        comm = sval("comm:status")
        if comm == "timeout":
            active.add("alarm:comm_timeout")
        elif comm == "disconnected":
            active.add("alarm:comm_disconnected")

        return active

    def _update_alarms(self) -> None:
        active_set = self._evaluate_thresholds()

        existing_keys: list[bytes] = self._redis.keys("alarm:*")
        all_keys = active_set | {k.decode() for k in existing_keys}

        pipe = self._redis.pipeline()
        for key in all_keys:
            if key in active_set:
                pipe.set(key, "1")
            else:
                pipe.delete(key)
        pipe.execute()


# ------------------------------------------------------------------
# Entry point

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CDU fake data simulator")
    parser.add_argument(
        "--scenario",
        default="normal",
        choices=list(SCENARIOS.keys()),
        help="Simulation scenario (default: normal)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between sensor updates (default: 2.0)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    cfg = get_config()
    if cfg.mode != "fake":
        log.info("Config mode is '%s', not 'fake'. Exiting.", cfg.mode)
        sys.exit(1)

    simulator = FakeDataSimulator(scenario=args.scenario, interval=args.interval)

    def _handle_signal(signum, frame):
        simulator.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    simulator.start()


if __name__ == "__main__":
    main()
