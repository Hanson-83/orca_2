"""多任务并行提交，以及状态查询。"""

from __future__ import annotations

import asyncio
import time

import httpx


async def _create(client: httpx.AsyncClient, name: str, workcell_id: str) -> str:
    response = await client.post(
        "/api/v1/tasks",
        json={
            "name": name,
            "protocol_ref": "plate_readout",
            "workcell_id": workcell_id,
            "run_mode": "MOCK",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    return body["id"]


async def _submit(client: httpx.AsyncClient, task_id: str) -> dict:
    response = await client.post(f"/api/v1/tasks/{task_id}/submit")
    assert response.status_code == 200, response.text
    return response.json()


async def test_two_tasks_run_in_parallel_and_can_be_queried(client: httpx.AsyncClient) -> None:
    first = await _create(client, "读数-A", "cell_a")
    second = await _create(client, "读数-B", "cell_b")
    submitted = await _submit(client, first)
    assert submitted["execution_ref"].startswith("mock-")
    assert submitted["mapping"]["orca_submit"]["path"] == "/executions"
    assert submitted["mapping"]["orca_submit"]["phase"] == "not_called"
    assert submitted["mapping"]["workflow_template_name"] == "plate_readout"
    await _submit(client, second)

    again = await client.post(f"/api/v1/tasks/{first}/submit")
    assert again.status_code == 409

    deadline = time.monotonic() + 3
    overlapped = False
    while time.monotonic() < deadline:
        left = (await client.get(f"/api/v1/tasks/{first}")).json()
        right = (await client.get(f"/api/v1/tasks/{second}")).json()
        if left["status"] == "running" and right["status"] == "running":
            cluster = (await client.get("/api/v1/cluster")).json()
            by_id = {cell["id"]: cell["status"] for cell in cluster["workcells"]}
            assert by_id["cell_a"] == "busy"
            assert by_id["cell_b"] == "busy"
            overlapped = True
            break
        if left["status"] in {"completed", "failed"} or right["status"] in {"completed", "failed"}:
            raise AssertionError(f"任务过早离开 running：{left['status']} {right['status']}")
        await asyncio.sleep(0.02)
    assert overlapped, "两条任务没有同时处于 running"

    for task_id in (first, second):
        done = None
        end = time.monotonic() + 3
        while time.monotonic() < end:
            done = (await client.get(f"/api/v1/tasks/{task_id}")).json()
            if done["status"] == "completed":
                break
            await asyncio.sleep(0.02)
        assert done is not None and done["status"] == "completed"

    listed = (await client.get("/api/v1/tasks", params={"status": "completed"})).json()
    ids = {row["id"] for row in listed}
    assert first in ids and second in ids


async def test_cancel_running_task(client: httpx.AsyncClient) -> None:
    task_id = await _create(client, "可取消", "cell_a")
    await _submit(client, task_id)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status = (await client.get(f"/api/v1/tasks/{task_id}")).json()["status"]
        if status == "running":
            break
        await asyncio.sleep(0.02)
    else:
        raise AssertionError("任务没有进入 running")

    cancelled = await client.post(f"/api/v1/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    await asyncio.sleep(0.2)
    again = await client.get(f"/api/v1/tasks/{task_id}")
    assert again.json()["status"] == "cancelled"


async def test_unknown_protocol_and_missing_task(client: httpx.AsyncClient) -> None:
    missing = await client.get("/api/v1/tasks/does-not-exist")
    assert missing.status_code == 404
    bad = await client.post(
        "/api/v1/tasks",
        json={
            "name": "未知协议",
            "protocol_ref": "not-registered",
            "workcell_id": "cell_a",
        },
    )
    assert bad.status_code == 404
    assert bad.json()["detail"]["code"] == "PROTOCOL_NOT_FOUND"


async def test_health_reports_no_auth(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["auth"] == "none"
    assert body["runtime"] == "mock"
