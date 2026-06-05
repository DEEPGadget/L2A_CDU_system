"""Control endpoints — mode / fan_curve / pump_duty CRUD.

The hash/key/channel names mirror those owned by
[src/local_ui/pages/settings_page.py](../../../local_ui/pages/settings_page.py)
so the Web UI and Local UI write to identical Redis state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from src.mcg import redis_keys as K
from src.web_ui.backend.pydantic_models import (
    DutyPayload,
    FanCurvePayload,
    ModePayload,
    PumpDutyPayload,
)
from src.web_ui.backend.redis_client import get_redis

router = APIRouter(prefix="/api/control", tags=["control"])

_DEFAULT_FAN_CURVE = {"min_temp": 25, "max_temp": 60, "min_duty": 100, "max_duty": 1000}
_DEFAULT_PUMP_DUTY = 600
_DEFAULT_MODE = "manual"   # startup default (see local_ui _STARTUP_DEFAULTS)

# Manual duty keys (UI % 0~100) + their startup defaults (see _STARTUP_DEFAULTS).
_DUTY_KEYS = {
    "pump_1": K.SENSOR_PUMP_PWM_DUTY_1, "pump_2": K.SENSOR_PUMP_PWM_DUTY_2,
    "fan_1": K.SENSOR_FAN_PWM_DUTY_1,   "fan_2": K.SENSOR_FAN_PWM_DUTY_2,
}
_DUTY_DEFAULTS = {"pump_1": 78, "pump_2": 78, "fan_1": 100, "fan_2": 100}


@router.get("")
async def get_all(r: Redis = Depends(get_redis)) -> dict:
    """Snapshot of every control:* key — used by Settings page on mount."""
    mode = await r.get(K.CONTROL_MODE) or _DEFAULT_MODE
    pump_raw = await r.get(K.CONTROL_PUMP_DUTY)
    fan_raw = await r.hgetall(K.CONTROL_FAN_CURVE)

    pump_duty = int(pump_raw) if pump_raw is not None else _DEFAULT_PUMP_DUTY

    fan_curve = dict(_DEFAULT_FAN_CURVE)
    for k in fan_curve:
        if k in fan_raw:
            try:
                fan_curve[k] = int(fan_raw[k])
            except ValueError:
                pass

    duty = dict(_DUTY_DEFAULTS)
    for field, key in _DUTY_KEYS.items():
        raw = await r.get(key)
        if raw is not None:
            try:
                duty[field] = int(float(raw))
            except ValueError:
                pass

    return {"mode": mode, "pump_duty": pump_duty, "fan_curve": fan_curve, "duty": duty}


@router.put("/mode")
async def put_mode(payload: ModePayload, r: Redis = Depends(get_redis)) -> dict:
    pipe = r.pipeline()
    pipe.set(K.CONTROL_MODE, payload.mode)
    pipe.publish(K.CH_CONTROL_MODE, payload.mode)
    await pipe.execute()
    return {"mode": payload.mode}


@router.put("/fan_curve")
async def put_fan_curve(
    payload: FanCurvePayload, r: Redis = Depends(get_redis),
) -> dict:
    mapping = {k: str(v) for k, v in payload.model_dump().items()}
    pipe = r.pipeline()
    pipe.hset(K.CONTROL_FAN_CURVE, mapping=mapping)
    pipe.publish(K.CH_CONTROL_FAN_CURVE_UPDATE, "1")
    await pipe.execute()
    return {"fan_curve": payload.model_dump()}


@router.put("/pump_duty")
async def put_pump_duty(
    payload: PumpDutyPayload, r: Redis = Depends(get_redis),
) -> dict:
    pipe = r.pipeline()
    pipe.set(K.CONTROL_PUMP_DUTY, str(payload.duty))
    pipe.publish(K.CH_CONTROL_PUMP_DUTY_UPDATE, str(payload.duty))
    await pipe.execute()
    return {"pump_duty": payload.duty}


@router.put("/duty")
async def put_duty(payload: DutyPayload, r: Redis = Depends(get_redis)) -> dict:
    """Manual per-actuator PWM duty → sensor:*_pwm_duty_* (UI %). MCG applies
    these only in manual mode. channel = key name, so all UIs sync via /ws."""
    applied: dict[str, int] = {}
    pipe = r.pipeline()
    for field, value in payload.model_dump().items():
        if value is None:
            continue
        key = _DUTY_KEYS[field]
        pipe.set(key, str(value))
        pipe.publish(key, str(value))
        applied[field] = value
    if applied:
        await pipe.execute()
    return {"duty": applied}
