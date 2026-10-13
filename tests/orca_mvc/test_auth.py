"""本机 Bearer。开放模式仍可用；设置令牌或 ORCA_MVC_AUTH=required 后必须带令牌。"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from orca_mvc.api.app import create_app
from orca_mvc.auth import AuthPolicy
from orca_mvc.mcp_server.client import ControlPlaneClient
from orca_mvc.services.control_plane import ControlPlane


async def _client(plane: ControlPlane) -> httpx.AsyncClient:
    app = create_app(plane)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_open_mode_allows_requests_and_reports_auth() -> None:
    plane = ControlPlane(auth=AuthPolicy.open(), step_delay=0.01, running_hold=0.01, poll_interval=0.01)
    await plane.startup()
    try:
        async with await _client(plane) as client:
            health = await client.get("/api/v1/health")
            assert health.status_code == 200
            body = health.json()
            assert body["auth"] == "none"
            assert body["auth_required"] is False
            tasks = await client.get("/api/v1/tasks")
            assert tasks.status_code == 200
    finally:
        await plane.shutdown()


async def test_token_required_rejects_missing_and_accepts_bearer() -> None:
    policy = AuthPolicy(mode="optional", token="lab-token", required=True, loopback=True)
    plane = ControlPlane(auth=policy, step_delay=0.01, running_hold=0.01, poll_interval=0.01)
    await plane.startup()
    try:
        async with await _client(plane) as client:
            health = await client.get("/api/v1/health")
            assert health.status_code == 200
            assert health.json()["auth"] == "bearer"
            assert health.json()["auth_required"] is True
            assert health.json()["auth_configured"] is True
            blocked = await client.get("/api/v1/tasks")
            assert blocked.status_code == 401
            assert blocked.json()["detail"]["code"] == "UNAUTHORIZED"
            wrong = await client.get("/api/v1/tasks", headers={"Authorization": "Bearer no"})
            assert wrong.status_code == 401
            ok = await client.get("/api/v1/tasks", headers={"Authorization": "Bearer lab-token"})
            assert ok.status_code == 200
    finally:
        await plane.shutdown()


async def test_required_without_token_is_not_silently_open() -> None:
    policy = AuthPolicy(mode="required", token=None, required=True, loopback=False)
    plane = ControlPlane(auth=policy, step_delay=0.01, running_hold=0.01, poll_interval=0.01)
    await plane.startup()
    try:
        async with await _client(plane) as client:
            health = await client.get("/api/v1/health")
            assert health.json()["auth_required"] is True
            assert health.json()["auth_configured"] is False
            blocked = await client.get("/api/v1/cluster")
            assert blocked.status_code == 401
            assert "ORCA_MVC_API_TOKEN" in blocked.json()["detail"]["message"]
    finally:
        await plane.shutdown()


async def _assert_sse_with_query_token(app: object) -> None:
    """httpx ASGITransport 会把 SSE 缓冲到结束，这里直接驱动 ASGI。"""

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
        "query_string": b"token=sse-token",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }

    async def receive() -> dict[str, str]:
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            headers = {key.decode().lower(): value.decode() for key, value in message.get("headers", [])}
            assert message["status"] == 200
            assert "text/event-stream" in headers.get("content-type", "")
        elif message["type"] == "http.response.body" and message.get("body"):
            chunks.append(message["body"])
            saw_body.set()

    sse_task = asyncio.create_task(app(scope, receive, send))  # type: ignore[operator]
    try:
        await asyncio.wait_for(saw_body.wait(), timeout=2)
        assert b"hello" in b"".join(chunks)
    finally:
        disconnected.set()
        if not sse_task.done():
            sse_task.cancel()
        try:
            await sse_task
        except asyncio.CancelledError:
            pass


async def test_events_accept_query_token_only() -> None:
    policy = AuthPolicy(mode="required", token="sse-token", required=True, loopback=True)
    plane = ControlPlane(auth=policy, step_delay=0.01, running_hold=0.01, poll_interval=0.01)
    await plane.startup()
    try:
        app = create_app(plane)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            missing = await client.get("/api/v1/events")
            assert missing.status_code == 401
            query_on_tasks = await client.get("/api/v1/tasks?token=sse-token")
            assert query_on_tasks.status_code == 401
        await _assert_sse_with_query_token(app)
    finally:
        await plane.shutdown()


def test_from_env_optional_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCA_MVC_API_TOKEN", raising=False)
    monkeypatch.setenv("ORCA_MVC_AUTH", "optional")
    monkeypatch.setenv("ORCA_MVC_HOST", "127.0.0.1")
    policy = AuthPolicy.from_env()
    assert policy.required is False
    assert policy.health_fields()["auth"] == "none"


def test_from_env_token_and_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORCA_MVC_API_TOKEN", "abc")
    monkeypatch.setenv("ORCA_MVC_AUTH", "optional")
    monkeypatch.setenv("ORCA_MVC_HOST", "127.0.0.1")
    assert AuthPolicy.from_env().required is True
    monkeypatch.delenv("ORCA_MVC_API_TOKEN", raising=False)
    monkeypatch.setenv("ORCA_MVC_HOST", "0.0.0.0")
    policy = AuthPolicy.from_env()
    assert policy.required is True
    assert policy.token is None


async def test_mcp_client_sends_bearer() -> None:
    policy = AuthPolicy(mode="required", token="mcp-token", required=True, loopback=True)
    plane = ControlPlane(auth=policy, step_delay=0.01, running_hold=0.01, poll_interval=0.01)
    await plane.startup()
    try:
        async with await _client(plane) as http:
            denied = ControlPlaneClient(http=http, token="")
            with pytest.raises(Exception):
                await denied.list_tasks()
            allowed = ControlPlaneClient(http=http, token="mcp-token")
            rows = await allowed.list_tasks()
            assert rows == []
    finally:
        await plane.shutdown()
