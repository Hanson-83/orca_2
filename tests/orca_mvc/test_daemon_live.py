"""可选：本机 daemon 已启动时探健康检查；拓扑和两条 workflow 都挂上之后再提交。

没有进程、或还没 mount / load 本夹具时跳过。不启动 daemon，CI 离线保持绿色。
"""

from __future__ import annotations

import httpx
import pytest

from examples.mvc_daemon_sim.specs import (
    PLATE_READOUT_WORKFLOW,
    SEAL_AND_SHAKE_WORKFLOW,
)
from orca_mvc.runtime.daemon_backend import OrcaDaemonBackend, resolve_daemon_base_url
from orca_mvc.services.control_plane import ControlPlane


def live_daemon_url(monkeypatch: pytest.MonkeyPatch) -> str:
    """撤掉测试夹具对 ORCA_DAEMON_HOME 的隔离，读开发者本机的 daemon。"""

    monkeypatch.undo()
    url = resolve_daemon_base_url()
    if not url:
        pytest.skip("没有 ORCA_DAEMON_URL，也没有 ~/.orca/daemon.json")
    try:
        response = httpx.get(f"{url}/health", timeout=0.4)
    except httpx.HTTPError as exc:
        pytest.skip(f"orca daemon 未在运行：{exc}")
    if response.status_code != 200:
        pytest.skip(f"daemon /health 返回 {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        pytest.skip("daemon /health 不是 JSON")
    if not isinstance(body, dict) or body.get("daemon") != "ok":
        pytest.skip("该地址不是 Orca daemon")
    return url


def test_optional_live_daemon_health(monkeypatch: pytest.MonkeyPatch) -> None:
    url = live_daemon_url(monkeypatch)
    body = httpx.get(f"{url}/health", timeout=0.4).json()
    assert body["daemon"] == "ok"


def _mounted_workflow_names(url: str) -> set[str]:
    try:
        response = httpx.get(f"{url}/catalog/workflows", timeout=2.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"读 catalog/workflows 失败：{exc}")
    if response.status_code == 409:
        pytest.skip("daemon 在跑，但还没有 mount topology")
    if response.status_code != 200:
        pytest.skip(f"catalog/workflows 返回 {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        pytest.skip("catalog/workflows 不是 JSON")
    if not isinstance(body, list):
        pytest.skip("catalog/workflows 不是列表")
    return {
        item.get("name")
        for item in body
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


async def test_optional_live_submit_list_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """daemon 上已有两条协议时：提交 plate_readout，列出执行，控制面取消（两段式 stop）。"""

    url = live_daemon_url(monkeypatch)
    names = _mounted_workflow_names(url)
    required = {PLATE_READOUT_WORKFLOW, SEAL_AND_SHAKE_WORKFLOW}
    missing = required - names
    if missing:
        pytest.skip(
            "daemon 已运行，但未挂载 "
            + ", ".join(sorted(missing))
            + "。在仓库根目录 load examples.mvc_daemon_sim 的两个 workflow"
        )

    backend = OrcaDaemonBackend(base_url=url, timeout=30.0)
    plane = ControlPlane(backend=backend, poll_interval=0.05)
    await plane.startup()
    try:
        task = await plane.create_task(
            name="live plate_readout",
            protocol_ref=PLATE_READOUT_WORKFLOW,
            workcell_id="cell_a",
        )
        submitted = await plane.submit_task(task.id)
        assert submitted.execution_ref
        execution_id = submitted.execution_ref
        rows = await backend.list_executions()
        assert any(row.get("id") == execution_id for row in rows), rows

        cancelled = await plane.cancel_task(task.id)
        assert cancelled.status.value == "cancelled"

        status = await backend.get_execution_status(execution_id)
        assert status == "cancelled", status
    finally:
        await plane.shutdown()
