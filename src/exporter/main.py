"""Redis → Prometheus exporter (pull).

Prometheus scrapes http://localhost:9003/metrics (job `sensor-exporter-0` in
/etc/prometheus/prometheus.yml). On each scrape we read the current Redis
`sensor:*` / `alarm:*` values and expose them as gauges, matching the metric
schema in docs/UI_Design.md (History section):

    sensor_coolant_temp_inlet{loop}      sensor_coolant_temp_outlet{loop}
    sensor_flow_rate{loop}               sensor_fan_rpm{loop}
    sensor_pump_pwm_duty{loop}           sensor_fan_pwm_duty{loop}
    sensor_water_level   sensor_ambient_temp   sensor_ambient_humidity
    sensor_leak          alarm_state{alarm}

Redis is the live-state DB; Prometheus is the history DB (pull path). This is
the Exporter side of docs/MCG.md §9 Prometheus (history). pH/conductivity are
intentionally not emitted (not measured in the current PCB revision).

Run: python -m src.exporter.main   (see scripts/services/cdu-exporter.service)
"""

from __future__ import annotations

import argparse
import logging
import time

import redis
from prometheus_client import REGISTRY, start_http_server
from prometheus_client.core import GaugeMetricFamily

log = logging.getLogger("exporter")

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
EXPORTER_PORT = 9003

# Per-loop sensor keys → (prometheus metric name, loop label).
_LOOP_METRICS: dict[str, tuple[str, str]] = {
    "sensor:coolant_temp_inlet_1":  ("sensor_coolant_temp_inlet", "1"),
    "sensor:coolant_temp_inlet_2":  ("sensor_coolant_temp_inlet", "2"),
    "sensor:coolant_temp_outlet_1": ("sensor_coolant_temp_outlet", "1"),
    "sensor:coolant_temp_outlet_2": ("sensor_coolant_temp_outlet", "2"),
    "sensor:flow_rate_1":           ("sensor_flow_rate", "1"),
    "sensor:flow_rate_2":           ("sensor_flow_rate", "2"),
    "sensor:fan_rpm_1":             ("sensor_fan_rpm", "1"),
    "sensor:fan_rpm_2":             ("sensor_fan_rpm", "2"),
    "sensor:pump_pwm_duty_1":       ("sensor_pump_pwm_duty", "1"),
    "sensor:pump_pwm_duty_2":       ("sensor_pump_pwm_duty", "2"),
    "sensor:fan_pwm_duty_1":        ("sensor_fan_pwm_duty", "1"),
    "sensor:fan_pwm_duty_2":        ("sensor_fan_pwm_duty", "2"),
}

# Branch flow keys → (loop, branch) labels for sensor_flow_rate_branch.
_BRANCH_FLOW_METRICS: dict[str, tuple[str, str]] = {
    "sensor:flow_rate_1_1": ("1", "1"),
    "sensor:flow_rate_1_2": ("1", "2"),
    "sensor:flow_rate_2_1": ("2", "1"),
    "sensor:flow_rate_2_2": ("2", "2"),
}

# Scalar (no loop label) sensor keys → metric name.
_SCALAR_METRICS: dict[str, str] = {
    "sensor:water_level":      "sensor_water_level",
    "sensor:ambient_temp":     "sensor_ambient_temp",
    "sensor:ambient_humidity": "sensor_ambient_humidity",
}

# Doc strings per metric (deduplicated).
_HELP = {
    "sensor_coolant_temp_inlet":  "Coolant inlet temperature (°C)",
    "sensor_coolant_temp_outlet": "Coolant outlet temperature (°C)",
    "sensor_flow_rate":           "Coolant flow rate (L/min)",
    "sensor_fan_rpm":             "Fan speed (RPM, per-loop average)",
    "sensor_pump_pwm_duty":       "Pump PWM duty (%)",
    "sensor_fan_pwm_duty":        "Fan PWM duty (%)",
    "sensor_flow_rate_branch":    "Per-branch coolant flow rate (L/min)",
    "sensor_water_level":         "Coolant level (2=HIGH 1=MIDDLE 0=LOW)",
    "sensor_ambient_temp":        "Device-internal temperature (°C)",
    "sensor_ambient_humidity":    "Device-internal humidity (% RH)",
    "sensor_leak":                "Leak state (0=NORMAL 1=LEAKED)",
}

_LEAK_MAP = {"NORMAL": 0.0, "LEAKED": 1.0}


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class RedisCollector:
    """Custom collector: queried by prometheus_client on every scrape."""

    def __init__(self, r: redis.Redis) -> None:
        self._r = r

    def collect(self):
        try:
            yield from self._collect()
        except redis.RedisError as exc:
            # Don't crash the scrape — just emit nothing this round.
            log.warning("Redis read failed during scrape: %s", exc)
            return

    def _collect(self):
        r = self._r

        # ── Per-loop gauges (one MetricFamily per metric, samples per loop) ──
        loop_keys = list(_LOOP_METRICS)
        loop_vals = r.mget(loop_keys)
        families: dict[str, GaugeMetricFamily] = {}
        for key, raw in zip(loop_keys, loop_vals):
            metric, loop = _LOOP_METRICS[key]
            val = _to_float(raw)
            if val is None:
                continue  # key absent / unparseable → no sample (no fabricated data)
            fam = families.get(metric)
            if fam is None:
                fam = GaugeMetricFamily(metric, _HELP.get(metric, metric), labels=["loop"])
                families[metric] = fam
            fam.add_metric([loop], val)
        yield from families.values()

        # ── Branch flow gauges (sensor_flow_rate_branch{loop,branch}) ──
        branch_keys = list(_BRANCH_FLOW_METRICS)
        branch_fam = GaugeMetricFamily(
            "sensor_flow_rate_branch", _HELP["sensor_flow_rate_branch"],
            labels=["loop", "branch"],
        )
        emitted = False
        for key, raw in zip(branch_keys, r.mget(branch_keys)):
            val = _to_float(raw)
            if val is None:
                continue
            loop, branch = _BRANCH_FLOW_METRICS[key]
            branch_fam.add_metric([loop, branch], val)
            emitted = True
        if emitted:
            yield branch_fam

        # ── Scalar gauges ──
        scalar_keys = list(_SCALAR_METRICS)
        for key, raw in zip(scalar_keys, r.mget(scalar_keys)):
            val = _to_float(raw)
            if val is None:
                continue
            metric = _SCALAR_METRICS[key]
            fam = GaugeMetricFamily(metric, _HELP.get(metric, metric))
            fam.add_metric([], val)
            yield fam

        # ── Leak (string → 0/1) ──
        leak_raw = r.get("sensor:leak")
        if leak_raw in _LEAK_MAP:
            fam = GaugeMetricFamily("sensor_leak", _HELP["sensor_leak"])
            fam.add_metric([], _LEAK_MAP[leak_raw])
            yield fam

        # ── Alarms: each existing alarm:<name> key → alarm_state{alarm}=1 ──
        alarm_fam = GaugeMetricFamily(
            "alarm_state", "Active alarm (1 when set in Redis)", labels=["alarm"]
        )
        for akey in r.scan_iter(match="alarm:*", count=200):
            name = akey.split(":", 1)[1] if ":" in akey else akey
            alarm_fam.add_metric([name], 1.0)
        yield alarm_fam


def main() -> None:
    parser = argparse.ArgumentParser(description="L2A CDU Redis→Prometheus exporter")
    parser.add_argument("--port", type=int, default=EXPORTER_PORT)
    parser.add_argument("--host", default=REDIS_HOST)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [exporter] %(levelname)s %(message)s",
    )

    r = redis.Redis(host=args.host, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    REGISTRY.register(RedisCollector(r))

    start_http_server(args.port)
    log.info("Exporter listening on :%d/metrics (Redis %s:%d)", args.port, args.host, REDIS_PORT)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
