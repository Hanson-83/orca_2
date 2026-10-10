"""MCP Server：把控制面收成 list_tasks / submit_task / get_status。

使用官方 Python SDK（mcp 2.x 的 MCPServer，即原先的 FastMCP）。
默认 stdio，不打开端口。若改成 streamable-http，绑定保持在 127.0.0.1。
"""

from __future__ import annotations

import json
from typing import Any

from orca_mvc.mcp_server.client import ControlPlaneClient


def build_server(api_url: str = "http://127.0.0.1:8100", client: ControlPlaneClient | None = None):
    """注册工具并返回 MCPServer。未安装 mcp 时抛出 ModuleNotFoundError。"""

    from mcp.server.mcpserver import MCPServer

    plane = client or ControlPlaneClient(api_url)
    server = MCPServer(
        "orca-mvc",
        instructions=(
            "Orca MVC Phase1 控制面工具。只应在本机使用，服务没有认证。"
            "不要把 MCP 或控制面暴露到公网。"
            "submit_task 会创建任务并立刻提交；执行面默认是模拟时间线。"
        ),
    )

    @server.tool(description="列出实验任务。status 可空，或 pending/queued/running/completed/failed/cancelled。")
    async def list_tasks(status: str | None = None) -> str:
        rows = await plane.list_tasks(status=status or None)
        return json.dumps(rows, ensure_ascii=False)

    @server.tool(description="创建并提交实验任务。返回任务 JSON，其中包含 id 与 status。")
    async def submit_task(
        name: str,
        protocol_ref: str,
        workcell_id: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        task = await plane.submit_task(
            name=name,
            protocol_ref=protocol_ref,
            workcell_id=workcell_id,
            params=params,
        )
        return json.dumps(task, ensure_ascii=False)

    @server.tool(description="按 task_id 查询实验任务状态，返回任务 JSON。")
    async def get_status(task_id: str) -> str:
        task = await plane.get_status(task_id)
        return json.dumps(task, ensure_ascii=False)

    @server.tool(description="从当前集群拓扑列出 workcell。")
    async def list_workcells() -> str:
        cells = await plane.list_workcells()
        return json.dumps(cells, ensure_ascii=False)

    return server
