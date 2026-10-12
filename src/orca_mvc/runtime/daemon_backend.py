"""Orca daemon 客户端骨架。

Phase 1 不发起 HTTP。路由表只收录在源码里核对过的路径，避免以后接线时编造 API。

对照来源（orca 2.2.0，src/orca/daemon）：

- ``routes.py`` ``POST /executions``
  请求体 SubmitWorkflowRequest：workflow_name、variables、run_mode
  （PURE_SIM / DEVICE_SIM / LIVE）、acknowledge_warnings、profile_path。
- ``operations_router.py``
  - ``GET  /operations/list-executions``
  - ``POST /operations/get-execution`` body ``{execution_id}``
  - ``POST /operations/get-execution-detail`` body ``{execution_id}``
  - ``POST /operations/stop-execution`` body ``{execution_id, confirm}``
    第一次调用暂停并把 abort 置为 armed；``confirm=true`` 的下一次才真正 abort。
  - ``POST /operations/remove-execution`` body ``{execution_id}``
- ``__main__.py`` 只绑定 ``127.0.0.1``，端口由 ``orca start`` 通过 ``--port`` 传入。
- ``lifecycle.py`` 把 ``{pid, port, started_at, spec?}`` 写到 ``~/.orca/daemon.json``
  （可用 ``ORCA_DAEMON_HOME`` 改目录）。上游没有固定的 8000 端口。

控制面的 ``MOCK`` 不是 daemon 的 run_mode。Phase 2 必须显式映射，不能原样提交。
"""

from __future__ import annotations

import os

from orca_mvc.models.task import ExperimentTask

# 方法 + 路径。测试会回读 daemon 源码，确认这些字符串真实存在。
DAEMON_ROUTE_CATALOG: dict[str, tuple[str, str]] = {
    "submit_workflow": ("POST", "/executions"),
    "list_executions": ("GET", "/operations/list-executions"),
    "get_execution": ("POST", "/operations/get-execution"),
    "get_execution_detail": ("POST", "/operations/get-execution-detail"),
    "stop_execution": ("POST", "/operations/stop-execution"),
    "remove_execution": ("POST", "/operations/remove-execution"),
}

DAEMON_RUN_MODES: tuple[str, ...] = ("PURE_SIM", "DEVICE_SIM", "LIVE")


class DaemonNotWired(Exception):
    """Phase 1 拒绝假装已经连上 daemon。"""


class OrcaDaemonBackend:
    """读取 ORCA_DAEMON_URL，但不调用。

    未设置该变量时 base_url 为 None。不要默认猜一个端口。
    """

    name = "orca-daemon"

    def __init__(self, base_url: str | None = None) -> None:
        if base_url is None:
            base_url = os.environ.get("ORCA_DAEMON_URL")
        self.base_url = base_url.rstrip("/") if base_url else None

    async def submit(self, task: ExperimentTask) -> str:
        raise self._not_wired("submit_workflow", task_id=task.id)

    async def get_execution_status(self, execution_ref: str) -> str:
        raise self._not_wired("get_execution", execution_ref=execution_ref)

    async def cancel(self, execution_ref: str) -> None:
        raise self._not_wired("stop_execution", execution_ref=execution_ref)

    def _not_wired(self, route_key: str, **context: str) -> DaemonNotWired:
        method, path = DAEMON_ROUTE_CATALOG[route_key]
        detail = " ".join(f"{key}={value}" for key, value in context.items())
        return DaemonNotWired(
            "Phase2 才连接 Orca daemon，本次没有发出请求。"
            f" 对照源码后的计划调用是 {method} {path}。"
            " 端口看 ~/.orca/daemon.json 的 port，或事先设置 ORCA_DAEMON_URL；"
            "不要假设 8000。"
            f" 当前 base_url={self.base_url!r}。{detail}"
        )
