"""Application config loader.

Reads config/config.yaml from the project root and exposes a singleton
AppConfig instance via get_config().
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import yaml

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "config.yaml")


@dataclass(frozen=True)
class AppConfig:
    mode: Literal["fake", "real"]


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    with open(_CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f)

    mode = data.get("mode", "fake")
    if mode not in ("fake", "real"):
        raise ValueError(f"config.yaml: invalid mode '{mode}'. Must be 'fake' or 'real'.")

    return AppConfig(mode=mode)
