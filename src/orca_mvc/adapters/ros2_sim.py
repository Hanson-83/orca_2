"""ROS2 联调适配：默认回放记录并走进程内总线。rclpy 可选，失败就退回总线。

``mode`` 始终是 ``sim``。即使本机能 import rclpy，这里也不声称连着机械臂。
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from orca_mvc.adapters.base import AdapterOffline
from orca_mvc.adapters.ros2_bus import Ros2MessageBus

logger = logging.getLogger("orca_mvc.adapters.ros2")

_TRACE = Path(__file__).resolve().parent.parent / "scenarios" / "ros2_trace.jsonl"
_DEFAULT_TOPICS = ("/workcell/arm/cmd", "/workcell/arm/state")
RclpyPublish = Callable[[str, dict[str, Any]], None]


class Ros2SimAdapter:
    def __init__(
        self,
        *,
        trace_path: Path | None = None,
        rclpy_publish: RclpyPublish | None = None,
    ) -> None:
        self._trace_path = trace_path or _TRACE
        self._rclpy_publish = rclpy_publish
        self._bus = Ros2MessageBus()
        self._status = "offline"
        self._log: list[dict[str, Any]] = []
        self._recorded = 0
        self._rclpy = "absent"
        self._backend = "message-bus"

    async def connect(self) -> None:
        self._rclpy = describe_rclpy()
        self._backend = "message-bus"
        self._replay()
        self._status = "online"
        logger.info("ros2 sim connected backend=%s rclpy=%s recorded=%s", self._backend, self._rclpy, self._recorded)

    async def disconnect(self) -> None:
        self._status = "offline"
        logger.info("ros2 sim disconnected")

    async def list_topics(self) -> list[str]:
        self._require_online()
        names = list(_DEFAULT_TOPICS)
        for topic in self._bus.topics():
            if topic not in names:
                names.append(topic)
        return names

    async def publish(self, topic: str, message: dict) -> None:
        self._require_online()
        self._bus.publish(
            topic,
            message,
            msg_type="orca_mvc/WorkcellCommand",
            source="call",
        )
        rclpy_state = self._side_publish(topic, message)
        entry = {
            "kind": "publish",
            "topic": topic,
            "message": message,
            "type": "orca_mvc/WorkcellCommand",
            "mode": "sim",
            "simulated": True,
            "backend": self._backend,
            "rclpy": rclpy_state,
        }
        self._log.append(entry)
        logger.info("ros2 sim publish topic=%s", topic)

    async def call_service(self, service: str, request: dict) -> dict:
        self._require_online()
        envelope = self._bus.call_service(
            service,
            request,
            msg_type="orca_mvc/Trigger",
        )
        entry = {
            "kind": "service",
            "service": service,
            "request": request,
            "response": envelope["response"],
            "type": envelope["type"],
            "mode": "sim",
            "simulated": True,
            "result": "ok",
            "backend": "message-bus",
        }
        self._log.append(entry)
        logger.info("ros2 sim service=%s", service)
        return dict(entry)

    def health(self) -> dict:
        return {
            "name": "ros2",
            "mode": "sim",
            "status": self._status,
            "backend": self._backend,
            "rclpy": self._rclpy,
            "call_count": len(self._log),
            "recorded_count": self._recorded,
            "recent_calls": list(self._log[-10:]),
        }

    def _replay(self) -> None:
        self._recorded = 0
        if not self._trace_path.is_file():
            return
        for line in self._trace_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if row.get("op") != "publish":
                continue
            self._bus.publish(
                str(row["topic"]),
                dict(row.get("data") or {}),
                msg_type=str(row.get("type") or "orca_mvc/Recorded"),
                source="recorded",
            )
            self._recorded += 1

    def _side_publish(self, topic: str, message: dict) -> str:
        """总线始终记下消息。rclpy 只在明确要求时旁路尝试。"""

        requested = os.environ.get("ORCA_MVC_ROS2", "bus").strip().lower() == "rclpy"
        if not requested and self._rclpy_publish is None:
            return self._rclpy
        publish = self._rclpy_publish or publish_via_rclpy
        try:
            publish(topic, message)
        except Exception as exc:
            self._rclpy = "degraded"
            self._backend = "message-bus"
            logger.warning("rclpy 发布失败，继续使用进程内总线：%s", exc)
            return "degraded"
        self._rclpy = "active"
        self._backend = "message-bus+rclpy"
        return "active"

    def _require_online(self) -> None:
        if self._status != "online":
            raise AdapterOffline("ros2")


def describe_rclpy() -> str:
    requested = os.environ.get("ORCA_MVC_ROS2", "bus").strip().lower() == "rclpy"
    try:
        importlib.import_module("rclpy")
    except Exception:
        return "degraded" if requested else "absent"
    if not requested:
        return "present-unused"
    return "available"


def publish_via_rclpy(topic: str, payload: dict[str, Any]) -> None:
    """尽力用 rclpy 发一条 std_msgs/String。失败由调用方降级。"""

    import rclpy
    from std_msgs.msg import String

    started = False
    if not rclpy.ok():
        rclpy.init(args=None)
        started = True
    node = rclpy.create_node("orca_mvc_ros2_sim")
    try:
        publisher = node.create_publisher(String, topic, 10)
        message = String()
        message.data = json.dumps(payload, ensure_ascii=False)
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=0.0)
    finally:
        node.destroy_node()
        if started:
            rclpy.shutdown()
