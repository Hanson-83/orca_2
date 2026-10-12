"""进程内话题/服务总线。信封接近 ROS2 的 topic、type、data，不走 DDS，也不需要机器人。"""

from __future__ import annotations

import time
from typing import Any


class Ros2MessageBus:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.services: list[dict[str, Any]] = []

    def publish(self, topic: str, data: dict[str, Any], *, msg_type: str, source: str) -> dict[str, Any]:
        envelope = {
            "op": "publish",
            "topic": topic,
            "type": msg_type,
            "data": data,
            "stamp_ns": time.time_ns(),
            "source": source,
        }
        self.published.append(envelope)
        return envelope

    def call_service(
        self,
        service: str,
        request: dict[str, Any],
        *,
        msg_type: str,
    ) -> dict[str, Any]:
        response = {"success": True, "message": "sim", "echo": request}
        envelope = {
            "op": "service",
            "service": service,
            "type": msg_type,
            "request": request,
            "response": response,
            "stamp_ns": time.time_ns(),
            "source": "call",
        }
        self.services.append(envelope)
        return envelope

    def topics(self) -> list[str]:
        names = [item["topic"] for item in self.published]
        return list(dict.fromkeys(names))
