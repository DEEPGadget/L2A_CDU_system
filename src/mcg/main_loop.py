"""MCG main loop - single thread, per-cycle Redis polling.

Mirrors the design recorded in docs/MCG.md sec 4:

    each cycle (single thread):
      step 1: read current mode (GET control:mode)
      step 2: reload Auto params (controller.reload() = HGETALL+GET) so the
              latest UI edits are picked up at most one cycle late
      step 3: emergency  -> TODO (post-system-stabilization)
      step 4: manual     -> write current desired duties to PCB
      step 5: poll PCB sensors -> Redis SET + flow derive
      step 6: auto       -> controller -> write fan + pump duties
      step 7: sleep(max(0, cycle - elapsed))

We do not subscribe to Pub/Sub here. At 1 Hz a HGETALL+GET round trip on
localhost is sub-millisecond, and pure GET polling is simpler and far more
robust than Pub/Sub timing (redis-py's get_message timing can drop messages
that arrived between two non-blocking reads). UI still PUBLISHes on every
write so other subscribers (Local UI direct, Web UI backend) get instant
updates - MCG just doesn't need that path.

Both Manual and Auto share the duty-mapper hard clamp (PCB.md "UI 0% bypass
risk" hazard mitigation).
"""

from __future__ import annotations

import logging
import time

import redis

from . import redis_keys as K
from .controller import AutoController
from .duty_mapper import ui_to_fan_hr, ui_to_pump_hr
from .modbus_client import PCB
from .polling import poll_once

log = logging.getLogger(__name__)

# Holding register addresses (control_board mapping, see MCG.md sec 9)
HR_PUMP_BASE = 0    # pump CH1~4  -> HR 0~3  (TIM1, 1 kHz)
HR_FAN_L1_BASE = 4  # fan L1 CH5~8  -> HR 4~7  (TIM2, 25 kHz)
HR_FAN_L2_BASE = 8  # fan L2 CH9~12 -> HR 8~11 (TIM8, 25 kHz)
FAN_CHANNELS_PER_LOOP = 4


# ── Mode + duty source ───────────────────────────────────────────────────────

def _read_mode(r: redis.Redis) -> str:
    raw = r.get(K.CONTROL_MODE)
    if raw is None:
        return "auto"
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    return raw


def _read_ui_duty(r: redis.Redis, key: str) -> float:
    raw = r.get(key)
    if raw is None:
        return 0.0
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


# ── PCB write helpers (use FC 16 = write_registers for atomic burst) ─────────

def _write_pumps(pcb: PCB, pump_l1_ui: float, pump_l2_ui: float) -> bool:
    hr_l1 = ui_to_pump_hr(pump_l1_ui)
    hr_l2 = ui_to_pump_hr(pump_l2_ui)
    # HR 0,1 = L1 (serial pair), HR 2,3 = L2 (serial pair). Same duty within a pair.
    return pcb.write_registers(HR_PUMP_BASE, [hr_l1, hr_l1, hr_l2, hr_l2])


def _write_fans(pcb: PCB, fan_l1_ui: float, fan_l2_ui: float) -> bool:
    hr_l1 = ui_to_fan_hr(fan_l1_ui)
    hr_l2 = ui_to_fan_hr(fan_l2_ui)
    # Burst write HR 4..11 = 8 channels (L1 CH5~8 + L2 CH9~12) in one transaction.
    return pcb.write_registers(
        HR_FAN_L1_BASE,
        [hr_l1] * FAN_CHANNELS_PER_LOOP + [hr_l2] * FAN_CHANNELS_PER_LOOP,
    )


# ── Comm state ───────────────────────────────────────────────────────────────

def _update_comm_state(
    r: redis.Redis,
    fail_count: int,
    timeout_n: int,
    disconnect_n: int,
) -> None:
    if fail_count == 0:
        status = "ok"
    elif fail_count >= disconnect_n:
        status = "disconnected"
    elif fail_count >= timeout_n:
        status = "timeout"
    else:
        status = "ok"
    pipe = r.pipeline()
    pipe.set(K.COMM_STATUS, status)
    pipe.set(K.COMM_CONSECUTIVE_FAILURES, str(fail_count))
    pipe.publish(K.COMM_STATUS, status)
    pipe.execute()


# ── Main loop ────────────────────────────────────────────────────────────────

def run(
    pcb: PCB,
    r: redis.Redis,
    cycle_seconds: float = 1.0,
    timeout_after_failures: int = 3,
    disconnected_after_failures: int = 10,
) -> None:
    """Block forever. Caller stops on KeyboardInterrupt / SIGTERM."""
    controller = AutoController(r)

    consecutive_fail = 0
    log.info("MCG main loop entering at %.2f s cadence", cycle_seconds)

    while True:
        t0 = time.monotonic()

        # ── step 1: current mode ──────────────────────────────────────────
        mode = _read_mode(r)

        # ── step 2: reload Auto params (cheap on localhost) ───────────────
        try:
            controller.reload()
        except Exception:
            log.exception("controller.reload() failed")

        # ── step 3: emergency (TODO) ──────────────────────────────────────
        if mode == "emergency":
            # Future: write 0 to all pump/fan; for now treat as no-op.
            pass

        # ── step 4: manual -> write desired duties from UI ────────────────
        if mode == "manual":
            try:
                p1 = _read_ui_duty(r, K.SENSOR_PUMP_PWM_DUTY_1)
                p2 = _read_ui_duty(r, K.SENSOR_PUMP_PWM_DUTY_2)
                f1 = _read_ui_duty(r, K.SENSOR_FAN_PWM_DUTY_1)
                f2 = _read_ui_duty(r, K.SENSOR_FAN_PWM_DUTY_2)
                _write_pumps(pcb, p1, p2)
                _write_fans(pcb, f1, f2)
            except Exception:
                log.exception("manual duty write failed")

        # ── step 5: poll PCB ──────────────────────────────────────────────
        ok = False
        try:
            ok = poll_once(pcb, r)
        except Exception:
            log.exception("poll_once raised")

        if ok:
            consecutive_fail = 0
        else:
            consecutive_fail += 1
            log.warning("PCB poll failed (consecutive %d)", consecutive_fail)

        try:
            _update_comm_state(r, consecutive_fail,
                                timeout_after_failures,
                                disconnected_after_failures)
        except Exception:
            log.exception("comm state update failed")

        # ── step 6: auto -> compute and write ─────────────────────────────
        if mode == "auto" and ok:
            try:
                outlet_l1 = _read_outlet(r, K.SENSOR_COOLANT_TEMP_OUTLET_1)
                outlet_l2 = _read_outlet(r, K.SENSOR_COOLANT_TEMP_OUTLET_2)
                fan_ui = controller.fan_duty_ui(outlet_l1, outlet_l2)
                pump_ui = controller.pump_duty_ui()
                _write_pumps(pcb, pump_ui, pump_ui)
                _write_fans(pcb, fan_ui, fan_ui)
                # Mirror the applied duties back to redis so UI shows the
                # value that is actually driving the PCB (Auto-mode feedback).
                pump_str = f"{pump_ui:.0f}"
                fan_str  = f"{fan_ui:.0f}"
                pipe = r.pipeline()
                for k, v in (
                    (K.SENSOR_PUMP_PWM_DUTY_1, pump_str),
                    (K.SENSOR_PUMP_PWM_DUTY_2, pump_str),
                    (K.SENSOR_FAN_PWM_DUTY_1,  fan_str),
                    (K.SENSOR_FAN_PWM_DUTY_2,  fan_str),
                ):
                    pipe.set(k, v)
                    pipe.publish(k, v)
                pipe.execute()
            except Exception:
                log.exception("auto compute/write failed")

        # ── step 7: sleep ─────────────────────────────────────────────────
        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, cycle_seconds - elapsed))


def _read_outlet(r: redis.Redis, key: str) -> float | None:
    raw = r.get(key)
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
