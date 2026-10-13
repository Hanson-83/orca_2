"""控制面 HTTP 客户端，供 MCP tools 调用。"""

from __future__ import annotations

import os
from typing import Any

import httpx


class ControlPlaneClientError(Exception):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"control plane HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class ControlPlaneClient:
    """base_url 指向已启动的控制面，例如 http://127.0.0.1:8100。

    测试可以传入绑了 ASGITransport 的 httpx.AsyncClient，这时请求走进程内应用。
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8100",
        http: httpx.AsyncClient | None = None,
        token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http
        if token is None:
            token = os.environ.get("ORCA_MVC_API_TOKEN", "")
        self._token = token.strip() or None

    async def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status} if status else None
        data = await self._request("GET", "/api/v1/tasks", params=params)
        if not isinstance(data, list):
            raise ControlPlaneClientError(500, "tasks response is not a list")
        return data

    async def submit_task(
        self,
        *,
        name: str,
        protocol_ref: str,
        workcell_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created = await self._request(
            "POST",
            "/api/v1/tasks",
            json={
                "name": name,
                "protocol_ref": protocol_ref,
                "workcell_id": workcell_id,
                "params": params or {},
            },
        )
        task_id = created["id"]
        submitted = await self._request("POST", f"/api/v1/tasks/{task_id}/submit")
        if not isinstance(submitted, dict):
            raise ControlPlaneClientError(500, "submit response is not an object")
        return submitted

    async def get_status(self, task_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/v1/tasks/{task_id}")
        if not isinstance(data, dict):
            raise ControlPlaneClientError(500, "task response is not an object")
        return data

    async def list_workcells(self) -> list[dict[str, Any]]:
        cluster = await self._request("GET", "/api/v1/cluster")
        cells = cluster["workcells"]
        if not isinstance(cells, list):
            raise ControlPlaneClientError(500, "workcells response is not a list")
        return cells

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._http is not None:
            response = await self._http.request(method, path, headers=headers, **kwargs)
        else:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
                response = await client.request(method, path, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise ControlPlaneClientError(response.status_code, response.text)
        return response.json()
