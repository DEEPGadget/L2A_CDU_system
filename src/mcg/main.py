"""MCG entrypoint.

Boot sequence:
  1. Load config/config.yaml
     - mode must be "real" (otherwise exit 1 so systemd Restart=on-failure
       does not loop)
     - read modbus port/baud/slave/timeout + loop cycle/comm thresholds
  2. Connect to Redis
  3. Try each Modbus serial port in config order; first one that responds
     to a probe read is kept
  4. Initialize comm:status = ok (overwrite any stale value from previous run)
  5. Hand off to main_loop.run() (blocks forever)

Run:
    python -m src.mcg.main
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

import redis

# Allow running directly: python src/mcg/main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config import get_config, get_loop_config, get_modbus_config
from src.mcg import redis_keys as K
from src.mcg.main_loop import run as run_main_loop
from src.mcg.modbus_client import open_pcb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mcg] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0


def main() -> int:
    t0 = time.monotonic()

    cfg = get_config()
    if cfg.mode != "real":
        log.info("config.mode is '%s', not 'real'. MCG exits without starting.",
                 cfg.mode)
        return 1

    modbus_cfg = get_modbus_config()
    loop_cfg = get_loop_config()

    log.info("MCG starting -- modbus ports=%s baud=%d slave=%d cycle=%.2fs",
             modbus_cfg.ports, modbus_cfg.baud, modbus_cfg.slave,
             loop_cfg.cycle_seconds)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

    # Connect to PCB - retry forever instead of exiting. This avoids systemd
    # restart-loop noise when the cable is unplugged or USB enumeration is
    # slow on boot, and lets us publish comm:status = disconnected so the UI
    # can show a meaningful state.
    pcb = None
    port = None
    retry_seconds = 5.0
    while pcb is None:
        pcb, port = open_pcb(
            ports=modbus_cfg.ports,
            baud=modbus_cfg.baud,
            slave=modbus_cfg.slave,
            timeout=modbus_cfg.timeout_seconds,
        )
        if pcb is not None:
            break
        log.error("PCB not found on any of %s @ %d, slave %d -- retry in %.0fs",
                  list(modbus_cfg.ports), modbus_cfg.baud, modbus_cfg.slave,
                  retry_seconds)
        try:
            pipe = r.pipeline()
            pipe.set(K.COMM_STATUS, "disconnected")
            pipe.publish(K.COMM_STATUS, "disconnected")
            pipe.execute()
        except Exception:
            pass
        time.sleep(retry_seconds)
    log.info("PCB connected on %s @ %d, slave %d (probe OK)",
             port, modbus_cfg.baud, modbus_cfg.slave)

    # PWM frequency init. PCB Flash default is 1 kHz for all three timers
    # (PCB.md "Flash 저장 항목"). For L2A Rev_C: fans on TIM2 need 25 kHz,
    # pumps on TIM8 need 1 kHz (Johnson eModule spec). TIM1 is unused.
    # Idempotent — safe to re-write every boot.
    try:
        pcb.write_register(13, 25000)  # HR 13 = TIM2 = fans @ 25 kHz
        pcb.write_register(14, 1000)   # HR 14 = TIM8 = pumps @ 1 kHz
        log.info("PWM freq init: TIM2=25 kHz (fan), TIM8=1 kHz (pump)")
    except Exception as e:
        log.warning("PWM freq init failed: %s", e)

    # Clear stale comm state from a previous run so the UI does not show
    # a red "disconnected" flash before the first poll cycle.
    try:
        pipe = r.pipeline()
        pipe.set(K.COMM_STATUS, "ok")
        pipe.set(K.COMM_CONSECUTIVE_FAILURES, "0")
        pipe.publish(K.COMM_STATUS, "ok")
        pipe.execute()
    except Exception as exc:
        log.warning("Could not initialize comm:status: %s", exc)

    log.info("MCG ready in %.2fs, entering main loop", time.monotonic() - t0)

    # Handle SIGTERM (systemd stop) gracefully -- pcb.close() in finally.
    def _on_signal(signum, _frame):
        log.info("Signal %d received, exiting", signum)
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    try:
        run_main_loop(
            pcb=pcb,
            r=r,
            cycle_seconds=loop_cfg.cycle_seconds,
            timeout_after_failures=loop_cfg.comm.timeout_after_failures,
            disconnected_after_failures=loop_cfg.comm.disconnected_after_failures,
        )
    except KeyboardInterrupt:
        log.info("MCG interrupted")
    finally:
        pcb.close()
        log.info("PCB closed, MCG exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
