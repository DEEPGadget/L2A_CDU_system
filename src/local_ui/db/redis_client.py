import redis

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0


class RedisClient:
    def __init__(self):
        self._r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
        )

    def get(self, key: str) -> str | None:
        return self._r.get(key)

    def get_all(self, keys: list[str]) -> dict:
        values = self._r.mget(keys)
        return {k: v for k, v in zip(keys, values)}

    def get_alarms(self) -> dict:
        alarm_keys = self._r.keys("alarm:*")
        if not alarm_keys:
            return {}
        values = self._r.mget(alarm_keys)
        return {k: v for k, v in zip(alarm_keys, values)}
