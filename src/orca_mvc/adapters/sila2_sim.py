"""通过 SiLA2 形状的 HTTP stub 调用命令。mode 固定为 sim：有线协议，没有设备。"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from orca_mvc.adapters.base import AdapterOffline, UnknownSilaCommand, UnknownSilaFeature
from orca_mvc.adapters.sila2_stub import create_sila2_stub_app

logger = logging.getLogger("orca_mvc.adapters.sila2")


class Sila2SimAdapter:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        env_url = os.environ.get("ORCA_MVC_SILA2_URL", "").strip()
        self._base_url = (base_url if base_url is not None else env_url) or None
        self._external = transport is not None or self._base_url is not None
        self._transport = transport
        self._status = "offline"
        self._log: list[dict[str, Any]] = []
        self._client: httpx.AsyncClient | None = None
        if not self._external:
            self._base_url = "http://sila2.stub"

    async def connect(self) -> None:
        client = self._ensure_client()
        try:
            response = await client.get("/sila/v1/features")
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._status = "offline"
            logger.warning("sila2 sim stub unreachable: %s", exc)
            return
        if not isinstance(body, dict) or not isinstance(body.get("features"), list):
            self._status = "offline"
            logger.warning("sila2 sim stub returned an unexpected feature list")
            return
        self._status = "online"
        logger.info("sila2 sim connected endpoint=%s", self._base_url)

    async def disconnect(self) -> None:
        self._status = "offline"
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("sila2 sim disconnected")

    async def list_features(self) -> list[str]:
        self._require_online()
        assert self._client is not None
        response = await self._client.get("/sila/v1/features")
        response.raise_for_status()
        body = response.json()
        names: list[str] = []
        for item in body.get("features", []):
            if isinstance(item, dict) and isinstance(item.get("featureIdentifier"), str):
                names.append(item["featureIdentifier"])
        return names

    async def call_command(self, feature: str, command: str, params: dict) -> dict:
        self._require_online()
        assert self._client is not None
        response = await self._client.post(
            f"/sila/v1/features/{feature}/commands/{command}",
            json={"parameters": params},
        )
        if response.status_code >= 400:
            self._raise_defined(feature, command, response)
        body = response.json()
        if body.get("executionStatus") != "finishedSuccessfully":
            raise RuntimeError(f"sila2 sim command did not finish: {body!r}")
        entry = {
            "feature": feature,
            "command": command,
            "params": params,
            "mode": "sim",
            "simulated": True,
            "result": "ok",
            "transport": "http-stub",
            "commandExecutionUUID": body.get("commandExecutionUUID"),
            "executionStatus": body.get("executionStatus"),
        }
        self._log.append(entry)
        logger.info("sila2 sim call feature=%s command=%s", feature, command)
        return dict(entry)

    def health(self) -> dict:
        return {
            "name": "sila2",
            "mode": "sim",
            "status": self._status,
            "transport": "http-stub",
            "endpoint": self._base_url,
            "call_count": len(self._log),
            "recent_calls": list(self._log[-10:]),
        }

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            transport = self._transport
            if not self._external:
                transport = httpx.ASGITransport(app=create_sila2_stub_app())
                self._transport = transport
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                transport=transport,
                timeout=5.0,
            )
        return self._client

    def _require_online(self) -> None:
        if self._status != "online" or self._client is None:
            raise AdapterOffline("sila2")

    @staticmethod
    def _raise_defined(feature: str, command: str, response: httpx.Response) -> None:
        try:
            body = response.json()
        except ValueError:
            body = {}
        identifier = body.get("errorIdentifier") if isinstance(body, dict) else None
        if identifier == "UnknownFeature":
            raise UnknownSilaFeature(feature)
        if identifier == "UnknownCommand":
            raise UnknownSilaCommand(feature, command)
        message = body.get("message") if isinstance(body, dict) else response.text
        raise RuntimeError(f"sila2 stub HTTP {response.status_code}: {message}")
