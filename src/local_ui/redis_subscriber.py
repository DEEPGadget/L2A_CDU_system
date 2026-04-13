"""Redis subscriber thread.

Subscribes to:
  - Pub/Sub channels  : sensor:*, comm:*  (simulator publishes on SET)
  - Keyspace events   : __keyevent@0__:set, __keyevent@0__:del
                        (used to detect alarm:* key creation / deletion)

Translates incoming messages into Qt signals so UI widgets can connect
directly without any threading concerns.

Keyspace notifications must be enabled in Redis:
    redis-cli config set notify-keyspace-events KEA
This is handled by main.py on startup.
"""

from __future__ import annotations

import logging

import redis
from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0


class RedisSubscriber(QThread):
    """Background thread that listens to Redis and emits Qt signals."""

    sensor_updated = Signal(str, str)   # (key, value)
    comm_updated = Signal(str, str)     # (key, value)
    alarm_set = Signal(str)             # alarm key
    alarm_deleted = Signal(str)         # alarm key

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = True

    def run(self) -> None:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        pubsub = r.pubsub()

        pubsub.psubscribe(
            "sensor:*",
            "comm:*",
            "__keyevent@0__:set",
            "__keyevent@0__:del",
        )

        log.info("RedisSubscriber listening.")
        try:
            for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] not in ("message", "pmessage"):
                    continue
                self._handle(message)
        except Exception as e:
            log.error("RedisSubscriber error: %s", e)
        finally:
            pubsub.close()

    def _handle(self, message: dict) -> None:
        channel: str = (
            message["channel"].decode()
            if isinstance(message["channel"], bytes)
            else message["channel"]
        )
        data: str = (
            message["data"].decode()
            if isinstance(message["data"], bytes)
            else str(message["data"])
        )

        # Keyspace events: channel = __keyevent@0__:set / :del
        #                  data    = the key that was modified
        if channel == "__keyevent@0__:set":
            if data.startswith("alarm:"):
                self.alarm_set.emit(data)
            return

        if channel == "__keyevent@0__:del":
            if data.startswith("alarm:"):
                self.alarm_deleted.emit(data)
            return

        # Pub/Sub channels: channel = sensor:xxx or comm:xxx
        #                   data    = the new value
        if channel.startswith("sensor:"):
            self.sensor_updated.emit(channel, data)
        elif channel.startswith("comm:"):
            self.comm_updated.emit(channel, data)

    def stop(self) -> None:
        self._running = False
        self.quit()
        self.wait()
