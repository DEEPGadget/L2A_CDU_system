"""Request body schemas with the same validation bounds the Local UI enforces.

Duty values are stored on Redis as the **x10 integer** (0~1000 scale,
0.1 % resolution), matching `control:pump_duty` / `control:fan_curve.*`
in [src/local_ui/pages/settings_page.py](../../local_ui/pages/settings_page.py).
The API works in the same scale so both UIs round-trip identically with
no risk of unit drift.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Operational lower bounds (docs/auto_control.md "L2A UI lower bounds"):
#   pump_input 17 % Nmin via 0.85x mapping -> UI 20 %  -> 200 raw
#   fan operational guideline                          -> UI 10 %  -> 100 raw
PUMP_DUTY_MIN_RAW = 200
FAN_DUTY_MIN_RAW  = 100
DUTY_MAX_RAW      = 1000


class FanCurvePayload(BaseModel):
    """control:fan_curve hash. 2-point linear interpolation."""

    min_temp: int = Field(ge=0, le=100)
    max_temp: int = Field(ge=0, le=100)
    min_duty: int = Field(ge=FAN_DUTY_MIN_RAW, le=DUTY_MAX_RAW)
    max_duty: int = Field(ge=FAN_DUTY_MIN_RAW, le=DUTY_MAX_RAW)

    @model_validator(mode="after")
    def _check_ordering(self) -> "FanCurvePayload":
        if self.min_temp >= self.max_temp:
            raise ValueError("min_temp must be < max_temp")
        if self.min_duty >= self.max_duty:
            raise ValueError("min_duty must be < max_duty")
        return self


class PumpDutyPayload(BaseModel):
    """control:pump_duty single integer (x10 scale)."""

    duty: int = Field(ge=PUMP_DUTY_MIN_RAW, le=DUTY_MAX_RAW)


class ModePayload(BaseModel):
    mode: Literal["auto", "manual", "emergency"]
