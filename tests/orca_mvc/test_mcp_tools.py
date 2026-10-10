"""MCP 工具包装控制面：submit_task 的返回里必须带任务 id。"""

from __future__ import annotations

import json

import httpx
import pytest

from orca_mvc.mcp_server.client import ControlPlaneClient


async def test_client_submit_returns_task_id(client: httpx.AsyncClient) -> None:
    tools = ControlPlaneClient(http=client)
    created = await tools.submit_task(
        name="MCP 直接客户端",
        protocol_ref="seal_and_shake",
        workcell_id="cell_b",
        params={"cycles": 2},
    )
    assert created["id"]
    assert created["status"] in {"queued", "running"}
    listed = await tools.list_tasks(status="queued")
    # 可能已经进入 running，两条查询至少有一条能看到它。
    running = await tools.list_tasks(status="running")
    ids = {row["id"] for row in listed + running}
    assert created["id"] in ids
    status = await tools.get_status(created["id"])
    assert status["id"] == created["id"]
    cells = await tools.list_workcells()
    assert {cell["id"] for cell in cells} >= {"cell_a", "cell_b"}


async def test_mcp_server_tools(client: httpx.AsyncClient) -> None:
    pytest.importorskip("mcp")
    from orca_mvc.mcp_server.server import build_server

    server = build_server(client=ControlPlaneClient(http=client))
    names = [tool.name for tool in await server.list_tools()]
    assert {"list_tasks", "submit_task", "get_status", "list_workcells"} <= set(names)

    result = await server.call_tool(
        "submit_task",
        {
            "name": "MCP 工具提交",
            "protocol_ref": "plate_readout",
            "workcell_id": "cell_a",
            "params": {"plate": "P1"},
        },
    )
    text = result.content[0].text
    payload = json.loads(text)
    assert payload["id"]
    assert payload["protocol_ref"] == "plate_readout"

    status_result = await server.call_tool("get_status", {"task_id": payload["id"]})
    status_payload = json.loads(status_result.content[0].text)
    assert status_payload["id"] == payload["id"]

    listed = json.loads((await server.call_tool("list_tasks", {})).content[0].text)
    assert any(row["id"] == payload["id"] for row in listed)
