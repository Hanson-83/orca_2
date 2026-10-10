"""SiLA2 mock：内存调用日志，不连接真实服务器。"""

from __future__ import annotations

import logging
from typing import Any

from orca_mvc.adapters.base import AdapterOffline

logger = logging.getLogger("orca_mvc.adapters.sila2")

_FEATURES = ("ShakerControl", "SealControl", "PlateReader")


class UnknownSilaFeature(Exception):
    """模拟目录里没有这个 Feature。控制面把它收成 4xx，而不是假装调用成功。"""

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(f"unknown SiLA2 feature: {feature}")


class Sila2MockAdapter:
    def __init__(self) -> None:
        self._status = "offline"
        self._log: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self._status = "online"
        logger.info("sila2 mock connected")

    async def disconnect(self) -> None:
        self._status = "offline"
        logger.info("sila2 mock disconnected")

    async def list_features(self) -> list[str]:
        self._require_online()
        return list(_FEATURES)

    async def call_command(self, feature: str, command: str, params: dict) -> dict:
        self._require_online()
        if feature not in _FEATURES:
            logger.info("sila2 mock reject unknown feature=%s", feature)
            raise UnknownSilaFeature(feature)
        entry = {
            "feature": feature,
            "command": command,
            "params": params,
            "simulated": True,
            "result": "ok",
        }
        self._log.append(entry)
        logger.info("sila2 mock call feature=%s command=%s", feature, command)
        return dict(entry)

    def health(self) -> dict:
        return {
            "name": "sila2",
            "mode": "mock",
            "status": self._status,
            "call_count": len(self._log),
            "recent_calls": list(self._log[-10:]),
        }

    def _require_online(self) -> None:
        if self._status != "online":
            raise AdapterOffline("sila2")
