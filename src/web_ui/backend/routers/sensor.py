from fastapi import APIRouter
import redis

router = APIRouter(prefix="/api/sensor", tags=["sensor"])

_r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

SENSOR_KEYS = [
    "sensor:coolant_temp_inlet",
    "sensor:coolant_temp_outlet",
    "sensor:ambient_temp",
    "sensor:ambient_humidity",
    "sensor:pressure",
    "sensor:flow_rate",
    "sensor:water_level",
    "sensor:leak",
    "sensor:pump_status",
    "sensor:fan_status",
]

COMM_KEYS = [
    "comm:status",
    "comm:consecutive_failures",
    "comm:last_error",
]


@router.get("/")
def get_all_sensors() -> dict:
    values = _r.mget(SENSOR_KEYS)
    return {k: v for k, v in zip(SENSOR_KEYS, values)}


@router.get("/alarms")
def get_alarms() -> dict:
    alarm_keys = _r.keys("alarm:*")
    if not alarm_keys:
        return {}
    values = _r.mget(alarm_keys)
    return {k: v for k, v in zip(alarm_keys, values)}


@router.get("/comm")
def get_comm_status() -> dict:
    values = _r.mget(COMM_KEYS)
    return {k: v for k, v in zip(COMM_KEYS, values)}
