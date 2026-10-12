"""SSE、lifespan 启动，以及 daemon 501 不发出 HTTP。"""

from __future__ import annotations

import asyncio
import time

import httpcore
import httpx
import pytest
from starlette.testclient import TestClient

from orca_mvc.api.app import create_app
from orca_mvc.runtime.daemon_backend import OrcaDaemonBackend
from orca_mvc.services.control_plane import ControlPlane


def test_lifespan_starts_runtime_and_health() -> None:
    """不预先 startup。TestClient 进入 lifespan 后，健康检查和默认集群都可用。"""
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "ok"
        assert body["auth"] == "none"
        assert body["runtime"] == "mock"
        cluster = client.get("/api/v1/cluster")
        assert cluster.status_code == 200
        assert len(cluster.json()["workcells"]) == 2


async def test_sse_hello_then_task_updated(plane: ControlPlane) -> None:
    """httpx ASGITransport 会缓冲到响应结束，SSE 用不了它。这里直接驱动 ASGI。"""
    app = create_app(plane)
    chunks: list[bytes] = []
    saw_body = asyncio.Event()
    disconnected = asyncio.Event()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/events",
        "raw_path": b"/api/v1/events",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }

    async def receive() -> dict[str, str]:
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            headers = {
                key.decode().lower(): value.decode()
                for key, value in message.get("headers", [])
            }
            assert message["status"] == 200
            assert "text/event-stream" in headers.get("content-type", "")
        elif message["type"] == "http.response.body" and message.get("body"):
            chunks.append(message["body"])
            saw_body.set()

    sse_task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(saw_body.wait(), timeout=2)
        opening = b"".join(chunks).decode()
        assert "event: hello" in opening
        assert '"ok": true' in opening

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            created = await http.post(
                "/api/v1/tasks",
                json={
                    "name": "SSE 观察",
                    "protocol_ref": "plate_readout",
                    "workcell_id": "cell_a",
                },
            )
            assert created.status_code == 201, created.text
            task_id = created.json()["id"]
            submitted = await http.post(f"/api/v1/tasks/{task_id}/submit")
            assert submitted.status_code == 200, submitted.text

        deadline = time.monotonic() + 2
        text = opening
        while time.monotonic() < deadline:
            text = b"".join(chunks).decode()
            if "event: task.updated" in text and task_id in text:
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError(text)
        assert "event: task.created" in text
    finally:
        disconnected.set()
        if not sse_task.done():
            sse_task.cancel()
        try:
            await sse_task
        except asyncio.CancelledError:
            pass


async def test_daemon_submit_returns_501_without_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCA_DAEMON_URL", raising=False)

    async def _block_async(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OrcaDaemonBackend 不应通过 httpcore 发出 HTTP")

    def _block_sync(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OrcaDaemonBackend 不应通过 httpcore 发出 HTTP")

    monkeypatch.setattr(httpcore.AsyncConnectionPool, "handle_async_request", _block_async)
    monkeypatch.setattr(httpcore.ConnectionPool, "handle_request", _block_sync)

    plane = ControlPlane(backend=OrcaDaemonBackend())
    await plane.startup()
    try:
        app = create_app(plane)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/tasks",
                json={
                    "name": "不应出网",
                    "protocol_ref": "plate_readout",
                    "workcell_id": "cell_a",
                },
            )
            assert created.status_code == 201, created.text
            task_id = created.json()["id"]
            submitted = await client.post(f"/api/v1/tasks/{task_id}/submit")
            assert submitted.status_code == 501
            detail = submitted.json()["detail"]
            assert detail["code"] == "DAEMON_NOT_WIRED"
            assert "MockRuntimeBackend" not in detail["message"]

            stored = (await client.get(f"/api/v1/tasks/{task_id}")).json()
            submit = stored["mapping"]["orca_submit"]
            assert submit["phase"] == "not_called"
            assert submit["path"] == "/executions"
            assert submit["code"] == "DAEMON_NOT_WIRED"
            assert "DAEMON_NOT_WIRED" in submit["reason"]
            assert "MockRuntimeBackend" not in submit["reason"]
            assert stored["status"] == "failed"
    finally:
        await plane.shutdown()
