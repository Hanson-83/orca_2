"""Orca daemon HTTP 客户端。

对照来源（orca 2.2.0，src/orca/daemon，本模块不导入上游包）：

- ``routes.py`` ``POST /executions``
  请求体 SubmitWorkflowRequest：workflow_name、variables、run_mode
  （PURE_SIM / DEVICE_SIM / LIVE）、acknowledge_warnings、profile_path。
  响应 ExecutionRecordDTO，执行 id 在 ``id``。
- ``operations_router.py``
  - ``GET  /operations/list-executions`` → ``{"executions": [...]}``
  - ``POST /operations/get-execution`` body ``{execution_id}``
    → ``{"execution": {id, workflow_name, status, ...}}``
    status 可能是 ExecutionPhase（accepting/draining/stopping/completed/failed/aborted）
    或 ExecutionState（running/completed/failed/aborted）。
  - ``POST /operations/get-execution-detail`` body ``{execution_id}``
  - ``POST /operations/stop-execution`` body ``{execution_id, confirm}``
    第一次（或尚未 armed）返回 ``status=armed`` 并暂停；``confirm=true`` 的下一次
    在仍暂停时才 abort，返回 ``status=aborted``。已结束则 ``already_terminal``。
  - ``POST /operations/remove-execution`` body ``{execution_id}``
- ``GET /health`` 在 daemon 进程活着时返回 ``{"daemon": "ok", ...}``。
- ``__main__.py`` 只绑定 ``127.0.0.1``。端口由 ``orca start`` 写入
  ``~/.orca/daemon.json`` 的 ``port``（目录可用 ``ORCA_DAEMON_HOME`` 改）。
  上游没有固定的 8000 端口。

控制面的 ``MOCK`` 映射为 daemon 的 ``PURE_SIM``。不能把 MOCK 原样提交。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from orca_mvc.models.enums import RunMode
from orca_mvc.models.task import ExperimentTask

logger = logging.getLogger("orca_mvc.runtime.daemon")

# 方法 + 路径。测试会回读 daemon 源码，确认这些字符串真实存在。
DAEMON_ROUTE_CATALOG: dict[str, tuple[str, str]] = {
    "submit_workflow": ("POST", "/executions"),
    "list_executions": ("GET", "/operations/list-executions"),
    "get_execution": ("POST", "/operations/get-execution"),
    "get_execution_detail": ("POST", "/operations/get-execution-detail"),
    "stop_execution": ("POST", "/operations/stop-execution"),
    "remove_execution": ("POST", "/operations/remove-execution"),
    "health": ("GET", "/health"),
}

DAEMON_RUN_MODES: tuple[str, ...] = ("PURE_SIM", "DEVICE_SIM", "LIVE")

# daemon 的 phase/state → 控制面 TaskStatus 字面量。
_DAEMON_STATUS_TO_TASK: dict[str, str] = {
    "accepting": "running",
    "draining": "running",
    "stopping": "running",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "aborted": "cancelled",
}

class DaemonError(Exception):
    """daemon 客户端失败。"""


class DaemonNotWired(DaemonError):
    """Phase 1 留下的类型。Phase 2 不再用它拒绝调用。"""


class DaemonUnavailable(DaemonError):
    """没有地址，或 TCP/HTTP 没有连上 daemon。"""

    def __init__(self, message: str, *, attempted: bool = False) -> None:
        super().__init__(message)
        self.attempted = attempted


class DaemonRequestError(DaemonError):
    """daemon 返回了 4xx/5xx，或响应形状对不上已核对的 schema。"""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class DaemonVariableError(DaemonError):
    """task.params 里有 daemon variables 不接受的值。"""


def daemon_info_path() -> Path:
    """``ORCA_DAEMON_HOME/daemon.json``，否则 ``~/.orca/daemon.json``。"""

    override = os.environ.get("ORCA_DAEMON_HOME")
    root = Path(override) if override else Path.home() / ".orca"
    return root / "daemon.json"


def read_daemon_port(path: Path | None = None) -> int | None:
    """读取 pid 文件里的 port。文件缺失或损坏时返回 None，不抛异常。"""

    target = path or daemon_info_path()
    if not target.is_file():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    port = raw.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        return None
    if not 1 <= port <= 65535:
        return None
    return port


def resolve_daemon_base_url(explicit: str | None = None) -> str | None:
    """显式参数 > ``ORCA_DAEMON_URL`` > daemon.json 的 port。

    都没有时返回 None。不要猜 8000。
    """

    if explicit is not None and explicit.strip():
        return explicit.strip().rstrip("/")
    env = os.environ.get("ORCA_DAEMON_URL", "").strip()
    if env:
        return env.rstrip("/")
    port = read_daemon_port()
    if port is None:
        return None
    return f"http://127.0.0.1:{port}"


def map_control_run_mode(run_mode: RunMode | str) -> str:
    """控制面 run_mode → daemon wire 值。``MOCK`` 固定映射为 ``PURE_SIM``。"""

    value = run_mode.value if isinstance(run_mode, RunMode) else str(run_mode)
    if value == RunMode.MOCK.value:
        return "PURE_SIM"
    if value in DAEMON_RUN_MODES:
        return value
    raise DaemonVariableError(f"无法映射到 daemon run_mode：{value}")


def map_daemon_status(status: str) -> str:
    """daemon execution status/phase → pending/queued/running/completed/failed/cancelled。"""

    try:
        return _DAEMON_STATUS_TO_TASK[status]
    except KeyError:
        raise DaemonRequestError(200, f"无法映射 daemon 状态 {status!r}") from None


def coerce_variables(params: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """收成 SubmitWorkflowRequest.variables 接受的标量。None 略去。"""

    variables: dict[str, str | int | float | bool] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool) or isinstance(value, (str, int, float)):
            variables[str(key)] = value
            continue
        raise DaemonVariableError(
            f"variables 只接受 str、int、float、bool，键 {key} 是 {type(value).__name__}"
        )
    return variables


def _detail_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        text = response.text.strip()
        return text or f"HTTP {response.status_code}"
    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("code")
        if message:
            return str(message)
    if isinstance(detail, str):
        return detail
    return f"HTTP {response.status_code}"


class OrcaDaemonBackend:
    """用 httpx 调用本机 Orca daemon。

    传入 ``transport``（例如 ``httpx.MockTransport``）时请求不会离开进程。
    """

    name = "orca-daemon"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 5.0,
        probe_timeout: float = 0.4,
    ) -> None:
        self.base_url = resolve_daemon_base_url(base_url)
        self._transport = transport
        self._timeout = timeout
        self._probe_timeout = probe_timeout
        self._client: httpx.AsyncClient | None = None
        self._probe_cache: tuple[float, bool] | None = None

    async def submit(self, task: ExperimentTask) -> str:
        mapping = task.mapping or {}
        workflow_name = mapping.get("workflow_template_name") or task.protocol_ref
        if not isinstance(workflow_name, str) or not workflow_name:
            raise DaemonVariableError("缺少 workflow_template_name，不能提交给 daemon")
        body: dict[str, Any] = {
            "workflow_name": workflow_name,
            "run_mode": map_control_run_mode(task.run_mode),
            "acknowledge_warnings": False,
        }
        variables = coerce_variables(task.params)
        if variables:
            body["variables"] = variables
        response = await self._request("POST", "/executions", json=body)
        self._raise_for_status(response)
        payload = _object(response)
        execution_id = payload.get("id")
        if not isinstance(execution_id, str) or not execution_id:
            raise DaemonRequestError(response.status_code, "POST /executions 响应缺少 id")
        logger.info(
            "daemon submit workflow=%s run_mode=%s execution_id=%s",
            workflow_name,
            body["run_mode"],
            execution_id,
        )
        return execution_id

    async def get_execution_status(self, execution_ref: str) -> str:
        response = await self._request(
            "POST",
            "/operations/get-execution",
            json={"execution_id": execution_ref},
        )
        if response.status_code == 404:
            raise KeyError(execution_ref)
        self._raise_for_status(response)
        payload = _object(response)
        execution = payload.get("execution")
        if not isinstance(execution, dict):
            raise DaemonRequestError(response.status_code, "get-execution 响应缺少 execution")
        status = execution.get("status")
        if not isinstance(status, str):
            raise DaemonRequestError(response.status_code, "get-execution 响应缺少 status")
        return map_daemon_status(status)

    async def cancel(self, execution_ref: str) -> None:
        """两段式停止：先 armed，再 ``confirm=true`` abort。"""

        first = await self._stop(execution_ref, confirm=False)
        if first == "armed":
            second = await self._stop(execution_ref, confirm=True)
            if second not in {"aborted", "already_terminal"}:
                raise DaemonRequestError(200, f"确认停止后状态异常：{second}")
            return
        if first not in {"aborted", "already_terminal"}:
            raise DaemonRequestError(200, f"停止返回未知状态：{first}")

    async def list_executions(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/operations/list-executions")
        self._raise_for_status(response)
        payload = _object(response)
        rows = payload.get("executions")
        if not isinstance(rows, list):
            raise DaemonRequestError(response.status_code, "list-executions 响应缺少 executions")
        return [row for row in rows if isinstance(row, dict)]

    async def daemon_health(self) -> tuple[str | None, bool]:
        """返回 ``(base_url, reachable)``。无地址时不发请求。"""

        if not self.base_url:
            return None, False
        now = time.monotonic()
        if self._probe_cache is not None and now - self._probe_cache[0] < 1.5:
            return self.base_url, self._probe_cache[1]
        reachable = False
        try:
            response = await self._request("GET", "/health", timeout=self._probe_timeout)
        except DaemonUnavailable:
            reachable = False
        else:
            if response.status_code == 200:
                try:
                    body = response.json()
                except (json.JSONDecodeError, ValueError):
                    body = None
                reachable = isinstance(body, dict) and body.get("daemon") == "ok"
        self._probe_cache = (now, reachable)
        return self.base_url, reachable

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _stop(self, execution_ref: str, *, confirm: bool) -> str:
        response = await self._request(
            "POST",
            "/operations/stop-execution",
            json={"execution_id": execution_ref, "confirm": confirm},
        )
        if response.status_code == 404:
            raise KeyError(execution_ref)
        self._raise_for_status(response)
        payload = _object(response)
        status = payload.get("status")
        if not isinstance(status, str):
            raise DaemonRequestError(response.status_code, "stop-execution 响应缺少 status")
        logger.info("daemon stop execution=%s confirm=%s status=%s", execution_ref, confirm, status)
        return status

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.base_url:
            raise DaemonUnavailable(_missing_url_message(), attempted=False)
        client = self._ensure_client()
        try:
            return await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DaemonUnavailable(
                f"无法连接 Orca daemon {self.base_url}：{exc}",
                attempted=True,
            ) from exc

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                transport=self._transport,
                timeout=self._timeout,
            )
        return self._client

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        raise DaemonRequestError(response.status_code, _detail_message(response))


def _object(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise DaemonRequestError(response.status_code, "daemon 响应不是 JSON") from exc
    if not isinstance(body, dict):
        raise DaemonRequestError(response.status_code, "daemon 响应不是对象")
    return body


def _missing_url_message() -> str:
    return (
        "没有 Orca daemon 地址。设置 ORCA_DAEMON_URL，"
        "或先运行 orca start，让 ~/.orca/daemon.json 写下 port。"
        "不要假设端口 8000。"
    )


async def probe_daemon(
    base_url: str,
    *,
    timeout: float = 0.4,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """``GET /health`` 且 ``daemon==ok`` 才算可达。失败返回 False。"""

    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        ) as client:
            response = await client.get("/health")
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(body, dict) and body.get("daemon") == "ok"

