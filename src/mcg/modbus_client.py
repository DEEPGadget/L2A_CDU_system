"""Modbus RTU client wrapper for the PCB (MCS_IO Board REV_C).

Thin facade over `pymodbus.client.ModbusSerialClient`. The wrapper:
  - tries a list of serial ports in order (USB CDC may surface as
    ttyACM0 or ttyUSB0 depending on enumeration order)
  - exposes simple `read_*` / `write_register` methods that return native
    Python values (None on failure)
  - keeps a single open serial connection - Modbus is a single-bus
    sequential protocol so this is intentional (no thread-safety needed,
    we run on a single main loop).

PCB DIP switch expected: DIP 1~5 OFF (slave ID = 1), DIP 6 ON (115200 baud).

Register map reference: docs/PCB.md "Modbus Registers".
"""

from __future__ import annotations

import logging
from typing import Sequence

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

log = logging.getLogger(__name__)


class PCB:
    """Single-PCB Modbus RTU client. One instance per L2A_CDU process."""

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        slave: int = 1,
        timeout: float = 1.0,
    ) -> None:
        self.port = port
        self.baud = int(baud)
        self.slave = int(slave)
        self.timeout = float(timeout)
        self._client: ModbusSerialClient | None = None

    # ── connection lifecycle ─────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            self._client = ModbusSerialClient(
                port=self.port,
                baudrate=self.baud,
                parity="N",
                stopbits=1,
                bytesize=8,
                timeout=self.timeout,
            )
            ok = self._client.connect()
            if not ok:
                log.warning("pymodbus connect() returned False for %s", self.port)
            return ok
        except Exception as exc:
            log.warning("Modbus connect error on %s: %s", self.port, exc)
            self._client = None
            return False

    def probe(self) -> bool:
        """Round-trip read of a known-safe register to verify the slave answers."""
        # HR 12 (PWM Freq TIM1) is R/W, always present, no side effect when read.
        ok = self.read_holding_registers(12, 1) is not None
        if not ok:
            log.warning("probe failed on %s @ %d (no Modbus response from slave %d)",
                        self.port, self.baud, self.slave)
        return ok

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    # ── reads ─────────────────────────────────────────────────────────────

    # pymodbus 3.12 API: slave kw is renamed to device_id, count is keyword-only.

    def read_input_registers(self, address: int, count: int) -> list[int] | None:
        if self._client is None:
            return None
        try:
            r = self._client.read_input_registers(address, count=count, device_id=self.slave)
            if r is None or r.isError():
                return None
            return list(r.registers)
        except ModbusException as exc:
            log.debug("read_input_registers(%s,%s) failed: %s", address, count, exc)
            return None
        except Exception as exc:
            log.debug("read_input_registers(%s,%s) unexpected: %s", address, count, exc)
            return None

    def read_holding_registers(self, address: int, count: int) -> list[int] | None:
        if self._client is None:
            return None
        try:
            r = self._client.read_holding_registers(address, count=count, device_id=self.slave)
            if r is None or r.isError():
                return None
            return list(r.registers)
        except ModbusException as exc:
            log.debug("read_holding_registers(%s,%s) failed: %s", address, count, exc)
            return None
        except Exception as exc:
            log.debug("read_holding_registers(%s,%s) unexpected: %s", address, count, exc)
            return None

    # ── writes ────────────────────────────────────────────────────────────

    def write_register(self, address: int, value: int) -> bool:
        if self._client is None:
            return False
        try:
            r = self._client.write_register(address, int(value), device_id=self.slave)
            return not (r is None or r.isError())
        except ModbusException as exc:
            log.debug("write_register(%s,%s) failed: %s", address, value, exc)
            return False
        except Exception as exc:
            log.debug("write_register(%s,%s) unexpected: %s", address, value, exc)
            return False

    def write_registers(self, address: int, values: Sequence[int]) -> bool:
        if self._client is None:
            return False
        try:
            r = self._client.write_registers(address, list(values), device_id=self.slave)
            return not (r is None or r.isError())
        except ModbusException as exc:
            log.debug("write_registers(%s,%s) failed: %s", address, list(values), exc)
            return False
        except Exception as exc:
            log.debug("write_registers(%s,%s) unexpected: %s", address, list(values), exc)
            return False


def open_pcb(ports: Sequence[str], baud: int, slave: int, timeout: float) -> tuple[PCB | None, str | None]:
    """Try `ports` in order. Returns (connected PCB, used port) or (None, None)."""
    for port in ports:
        pcb = PCB(port=port, baud=baud, slave=slave, timeout=timeout)
        if pcb.connect() and pcb.probe():
            return pcb, port
        pcb.close()
    return None, None
