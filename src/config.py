"""Application config loader.

Reads config/config.yaml from the project root and exposes typed accessors.
get_modbus_config() / get_loop_config() are cached (lru_cache(1)) from the
same file read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import yaml

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "config.yaml")


@dataclass(frozen=True)
class ModbusConfig:
    ports: tuple[str, ...]      # try in order, first success wins
    baud: int
    slave: int
    timeout_seconds: float


@dataclass(frozen=True)
class CommConfig:
    timeout_after_failures: int
    disconnected_after_failures: int


@dataclass(frozen=True)
class LoopConfig:
    cycle_seconds: float
    comm: CommConfig


def _load_raw() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_modbus_config() -> ModbusConfig:
    data = _load_raw().get("modbus") or {}
    port = data.get("port")
    if port is None:
        raise ValueError("config.yaml: modbus.port missing")
    if isinstance(port, str):
        ports = (port,)
    else:
        ports = tuple(str(p) for p in port)
        if not ports:
            raise ValueError("config.yaml: modbus.port list is empty")
    return ModbusConfig(
        ports=ports,
        baud=int(data.get("baud", 115200)),
        slave=int(data.get("slave", 1)),
        timeout_seconds=float(data.get("timeout_seconds", 1.0)),
    )


@lru_cache(maxsize=1)
def get_loop_config() -> LoopConfig:
    data = _load_raw().get("loop") or {}
    comm_data = data.get("comm") or {}
    return LoopConfig(
        cycle_seconds=float(data.get("cycle_seconds", 1.0)),
        comm=CommConfig(
            timeout_after_failures=int(comm_data.get("timeout_after_failures", 3)),
            disconnected_after_failures=int(comm_data.get("disconnected_after_failures", 10)),
        ),
    )
