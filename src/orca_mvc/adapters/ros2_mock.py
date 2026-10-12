"""ROS2 mock：内存话题与服务调用，不启动 rclpy。"""

from __future__ import annotations

import logging
from typing import Any

from orca_mvc.adapters.base import AdapterOffline

logger = logging.getLogger("orca_mvc.adapters.ros2")

_TOPICS = ("/workcell/arm/cmd", "/workcell/arm/state")


class Ros2MockAdapter:
    def __init__(self) -> None:
        self._status = "offline"
        self._log: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self._status = "online"
        logger.info("ros2 mock connected")

    async def disconnect(self) -> None:
        self._status = "offline"
        logger.info("ros2 mock disconnected")

    async def list_topics(self) -> list[str]:
        self._require_online()
        return list(_TOPICS)

    async def publish(self, topic: str, message: dict) -> None:
        self._require_online()
        entry = {
            "kind": "publish",
            "topic": topic,
            "message": message,
            "simulated": True,
        }
        self._log.append(entry)
        logger.info("ros2 mock publish topic=%s", topic)

    async def call_service(self, service: str, request: dict) -> dict:
        self._require_online()
        entry = {
            "kind": "service",
            "service": service,
            "request": request,
            "simulated": True,
            "result": "ok",
        }
        self._log.append(entry)
        logger.info("ros2 mock service=%s", service)
        return dict(entry)

    def health(self) -> dict:
        return {
            "name": "ros2",
            "mode": "mock",
            "status": self._status,
            "call_count": len(self._log),
            "recent_calls": list(self._log[-10:]),
        }

    def _require_online(self) -> None:
        if self._status != "online":
            raise AdapterOffline("ros2")
