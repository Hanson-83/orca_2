"""进程内控制面：任务、集群、适配器、执行后端。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from orca_mvc.adapters.base import AdapterOffline
from orca_mvc.adapters.ros2_mock import Ros2MockAdapter
from orca_mvc.adapters.sila2_mock import Sila2MockAdapter
from orca_mvc.models.cluster import CellLink, Cluster, ClusterView, Transfer, Workcell
from orca_mvc.models.enums import RunMode, TaskStatus, TransferState, WorkcellStatus
from orca_mvc.models.protocol import ProtocolMapping
from orca_mvc.models.task import ExperimentTask
from orca_mvc.runtime.base import RuntimeBackend
from orca_mvc.runtime.daemon_backend import DAEMON_ROUTE_CATALOG, DaemonNotWired, OrcaDaemonBackend
from orca_mvc.runtime.mock_backend import MockRuntimeBackend
from orca_mvc.store.memory import MemoryTaskStore

logger = logging.getLogger("orca_mvc.control")

_TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
_CANCELLABLE = {TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING}

_BUNDLED_SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "cluster_two_cells.json"

_DEFAULT_PROTOCOLS = (
    ProtocolMapping(
        name="plate_readout",
        workflow_template_name="plate_readout",
        description="示例：培养板读数",
    ),
    ProtocolMapping(
        name="seal_and_shake",
        workflow_template_name="seal_and_shake",
        description="示例：封膜并振荡",
    ),
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ControlPlaneError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


class ControlPlane:
    """MVC 的 Model + 应用服务。HTTP 与 MCP 都调用这里。"""

    def __init__(
        self,
        *,
        backend: RuntimeBackend | None = None,
        step_delay: float = 0.2,
        running_hold: float = 0.6,
        poll_interval: float = 0.1,
        transfer_step: float = 0.2,
        scenario_path: Path | None = None,
        sila2: Sila2MockAdapter | None = None,
        ros2: Ros2MockAdapter | None = None,
    ) -> None:
        self._backend = backend or MockRuntimeBackend(
            step_delay=step_delay,
            running_hold=running_hold,
        )
        self._poll_interval = poll_interval
        self._transfer_step = transfer_step
        self._scenario_path = scenario_path or _BUNDLED_SCENARIO
        self._tasks = MemoryTaskStore()
        self._protocols: dict[str, ProtocolMapping] = {
            item.name: item for item in _DEFAULT_PROTOCOLS
        }
        self._cluster: Cluster | None = None
        self._transfers: list[Transfer] = []
        self._sila2 = sila2 or Sila2MockAdapter()
        self._ros2 = ros2 or Ros2MockAdapter()
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._jobs: set[asyncio.Task[None]] = set()
        self._started = False

    @classmethod
    def from_env(cls) -> ControlPlane:
        runtime = os.environ.get("ORCA_MVC_RUNTIME", "mock")
        step_delay = float(os.environ.get("ORCA_MVC_STEP_DELAY", "0.2"))
        running_hold = float(os.environ.get("ORCA_MVC_RUNNING_HOLD", "0.6"))
        if runtime == "daemon":
            backend: RuntimeBackend = OrcaDaemonBackend()
        elif runtime == "mock":
            backend = MockRuntimeBackend(step_delay=step_delay, running_hold=running_hold)
        else:
            raise ControlPlaneError(
                500,
                "BAD_RUNTIME",
                f"未知 ORCA_MVC_RUNTIME={runtime!r}，只接受 mock 或 daemon",
            )
        return cls(
            backend=backend,
            step_delay=step_delay,
            running_hold=running_hold,
            poll_interval=float(os.environ.get("ORCA_MVC_POLL_INTERVAL", "0.1")),
            transfer_step=float(os.environ.get("ORCA_MVC_TRANSFER_STEP", "0.2")),
        )

    @property
    def runtime_name(self) -> str:
        return self._backend.name

    async def startup(self) -> None:
        if self._started:
            return
        self._started = True
        if self._cluster is None and self._scenario_path.is_file():
            payload = json.loads(self._scenario_path.read_text(encoding="utf-8"))
            self.load_cluster(payload)
        await self._sila2.connect()
        await self._ros2.connect()
        logger.info("control plane ready runtime=%s", self.runtime_name)

    async def shutdown(self) -> None:
        jobs = list(self._jobs)
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        closer = getattr(self._backend, "aclose", None)
        if closer is not None:
            await closer()
        await self._sila2.disconnect()
        await self._ros2.disconnect()
        self._started = False

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def list_protocols(self) -> list[ProtocolMapping]:
        return [item.model_copy(deep=True) for item in self._protocols.values()]

    async def create_task(
        self,
        *,
        name: str,
        protocol_ref: str,
        workcell_id: str,
        run_mode: RunMode = RunMode.MOCK,
        params: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> ExperimentTask:
        async with self._tasks.lock:
            self._require_protocol(protocol_ref)
            self._require_workcell(workcell_id)
            now = utcnow()
            task = ExperimentTask(
                id=uuid4().hex,
                name=name,
                protocol_ref=protocol_ref,
                workcell_id=workcell_id,
                run_mode=run_mode,
                params=dict(params or {}),
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            self._tasks.insert(task)
            snapshot = task.model_copy(deep=True)
        self._emit("task.created", snapshot.model_dump(mode="json"))
        logger.info("task created id=%s protocol=%s cell=%s", snapshot.id, protocol_ref, workcell_id)
        return snapshot

    async def list_tasks(self, status: TaskStatus | None = None) -> list[ExperimentTask]:
        async with self._tasks.lock:
            return self._tasks.list(status)

    async def get_task(self, task_id: str) -> ExperimentTask:
        async with self._tasks.lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise ControlPlaneError(404, "TASK_NOT_FOUND", f"任务不存在：{task_id}")
        return task

    async def submit_task(self, task_id: str) -> ExperimentTask:
        async with self._tasks.lock:
            try:
                task = self._tasks.require_live(task_id)
            except KeyError:
                raise ControlPlaneError(404, "TASK_NOT_FOUND", f"任务不存在：{task_id}") from None
            if task.status != TaskStatus.PENDING:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE",
                    f"任务 {task_id} 当前是 {task.status.value}，只有 pending 可以提交",
                )
            protocol = self._require_protocol(task.protocol_ref)
            self._require_workcell(task.workcell_id)
            method, path = DAEMON_ROUTE_CATALOG["submit_workflow"]
            task.status = TaskStatus.QUEUED
            task.updated_at = utcnow()
            task.mapping = {
                "protocol_ref": protocol.name,
                "workflow_template_name": protocol.workflow_template_name,
                "run_mode": task.run_mode.value,
                "orca_submit": {
                    "method": method,
                    "path": path,
                    "body_keys": ["workflow_name", "variables", "run_mode"],
                    "phase": "not_called",
                    "reason": "Phase1 MockRuntimeBackend 只模拟时间线，不请求 daemon",
                },
            }
            pending = task.model_copy(deep=True)

        try:
            ref = await self._backend.submit(pending)
        except DaemonNotWired as exc:
            await self._mark_failed(task_id, str(exc))
            raise ControlPlaneError(501, "DAEMON_NOT_WIRED", str(exc)) from exc
        except Exception as exc:
            await self._mark_failed(task_id, str(exc))
            logger.exception("submit failed task=%s", task_id)
            raise ControlPlaneError(502, "RUNTIME_SUBMIT_FAILED", str(exc), retryable=True) from exc

        async with self._tasks.lock:
            task = self._tasks.require_live(task_id)
            task.execution_ref = ref
            task.updated_at = utcnow()
            snapshot = task.model_copy(deep=True)
        self._emit("task.updated", snapshot.model_dump(mode="json"))
        self._track(self._watch(task_id, ref))
        logger.info("task submitted id=%s execution_ref=%s", task_id, ref)
        return snapshot

    async def cancel_task(self, task_id: str) -> ExperimentTask:
        async with self._tasks.lock:
            try:
                task = self._tasks.require_live(task_id)
            except KeyError:
                raise ControlPlaneError(404, "TASK_NOT_FOUND", f"任务不存在：{task_id}") from None
            if task.status not in _CANCELLABLE:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE",
                    f"任务 {task_id} 当前是 {task.status.value}，不能取消",
                )
            ref = task.execution_ref
            task.status = TaskStatus.CANCELLED
            task.updated_at = utcnow()
            snapshot = task.model_copy(deep=True)
        if ref is not None:
            try:
                await self._backend.cancel(ref)
            except DaemonNotWired as exc:
                raise ControlPlaneError(501, "DAEMON_NOT_WIRED", str(exc)) from exc
            except KeyError:
                logger.warning("cancel missing execution_ref=%s", ref)
        self._emit("task.updated", snapshot.model_dump(mode="json"))
        logger.info("task cancelled id=%s", task_id)
        return snapshot

    def load_cluster(self, payload: dict[str, Any]) -> ClusterView:
        cluster = self._parse_cluster(payload)
        self._cluster = cluster
        self._transfers.clear()
        view = self._cluster_view()
        self._emit("cluster.loaded", {"id": cluster.id, "workcells": len(cluster.workcells)})
        logger.info("cluster loaded id=%s cells=%s", cluster.id, len(cluster.workcells))
        return view

    def get_cluster(self) -> ClusterView:
        if self._cluster is None:
            raise ControlPlaneError(409, "NO_CLUSTER", "尚未加载集群拓扑")
        return self._cluster_view()

    async def request_transfer(self, *, labware_id: str, from_cell: str, to_cell: str) -> Transfer:
        if self._cluster is None:
            raise ControlPlaneError(409, "NO_CLUSTER", "尚未加载集群拓扑")
        link = self._find_link(from_cell, to_cell)
        if link is None:
            raise ControlPlaneError(
                409,
                "NO_LINK",
                f"没有从 {from_cell} 到 {to_cell} 的链路，不能创建转运占位",
            )
        now = utcnow()
        transfer = Transfer(
            transfer_id=uuid4().hex,
            labware_id=labware_id,
            from_cell=from_cell,
            to_cell=to_cell,
            state=TransferState.REQUESTED,
            created_at=now,
            updated_at=now,
        )
        self._transfers.append(transfer)
        snapshot = transfer.model_copy(deep=True)
        self._emit("transfer.updated", snapshot.model_dump(mode="json"))
        self._track(self._advance_transfer(transfer.transfer_id))
        logger.info(
            "transfer requested id=%s %s -> %s via %s",
            transfer.transfer_id,
            from_cell,
            to_cell,
            link.link_id,
        )
        return snapshot

    def list_transfers(self) -> list[Transfer]:
        return [item.model_copy(deep=True) for item in self._transfers]

    def adapter_health(self) -> dict[str, dict[str, Any]]:
        return {"sila2": self._sila2.health(), "ros2": self._ros2.health()}

    async def call_sila2(self, feature: str, command: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self._sila2.call_command(feature, command, params)
        except AdapterOffline as exc:
            raise ControlPlaneError(409, "ADAPTER_OFFLINE", "SiLA2 mock 未连接", retryable=True) from exc
        self._emit("adapter.called", {"name": "sila2", "command": command})
        return result

    async def call_ros2(
        self,
        *,
        kind: str,
        service: str | None,
        topic: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            if kind == "publish":
                if not topic:
                    raise ControlPlaneError(422, "BAD_REQUEST", "publish 需要 topic")
                await self._ros2.publish(topic, payload)
                result = {"kind": "publish", "topic": topic, "simulated": True}
            elif kind == "service":
                if not service:
                    raise ControlPlaneError(422, "BAD_REQUEST", "service 调用需要 service")
                result = await self._ros2.call_service(service, payload)
            else:
                raise ControlPlaneError(422, "BAD_REQUEST", f"未知 kind：{kind}")
        except AdapterOffline as exc:
            raise ControlPlaneError(409, "ADAPTER_OFFLINE", "ROS2 mock 未连接", retryable=True) from exc
        self._emit("adapter.called", {"name": "ros2", "kind": kind})
        return result

    async def _watch(self, task_id: str, execution_ref: str) -> None:
        try:
            while True:
                raw = await self._backend.get_execution_status(execution_ref)
                try:
                    status = TaskStatus(raw)
                except ValueError:
                    status = TaskStatus.FAILED
                changed: ExperimentTask | None = None
                async with self._tasks.lock:
                    try:
                        task = self._tasks.require_live(task_id)
                    except KeyError:
                        return
                    if task.status in _TERMINAL:
                        return
                    if task.status != status:
                        task.status = status
                        task.updated_at = utcnow()
                        if status == TaskStatus.FAILED and not task.error:
                            task.error = "执行面报告失败"
                        changed = task.model_copy(deep=True)
                if changed is not None:
                    self._emit("task.updated", changed.model_dump(mode="json"))
                if status in _TERMINAL:
                    return
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("watcher failed task=%s", task_id)
            await self._mark_failed(task_id, "状态同步失败")

    async def _advance_transfer(self, transfer_id: str) -> None:
        for state in (TransferState.IN_TRANSIT, TransferState.ARRIVED):
            await asyncio.sleep(self._transfer_step)
            target = next((item for item in self._transfers if item.transfer_id == transfer_id), None)
            if target is None or target.state == TransferState.FAILED:
                return
            target.state = state
            target.updated_at = utcnow()
            self._emit("transfer.updated", target.model_dump(mode="json"))

    async def _mark_failed(self, task_id: str, message: str) -> None:
        async with self._tasks.lock:
            try:
                task = self._tasks.require_live(task_id)
            except KeyError:
                return
            if task.status in _TERMINAL:
                return
            task.status = TaskStatus.FAILED
            task.error = message
            task.updated_at = utcnow()
            snapshot = task.model_copy(deep=True)
        self._emit("task.updated", snapshot.model_dump(mode="json"))

    def _cluster_view(self) -> ClusterView:
        assert self._cluster is not None
        running = {
            task.workcell_id
            for task in self._tasks.list()
            if task.status == TaskStatus.RUNNING
        }
        cells: list[Workcell] = []
        for cell in self._cluster.workcells:
            if cell.status in {WorkcellStatus.FAULT, WorkcellStatus.OFFLINE}:
                live = cell.status
            else:
                live = WorkcellStatus.BUSY if cell.id in running else WorkcellStatus.IDLE
            cells.append(cell.model_copy(update={"status": live}))
        return ClusterView(
            id=self._cluster.id,
            workcells=cells,
            links=list(self._cluster.links),
            transfers=self.list_transfers(),
        )

    def _parse_cluster(self, payload: dict[str, Any]) -> Cluster:
        try:
            cluster = Cluster.model_validate(payload)
        except Exception as exc:
            raise ControlPlaneError(422, "BAD_CLUSTER", f"拓扑无法解析：{exc}") from exc
        ids = [cell.id for cell in cluster.workcells]
        if not ids:
            raise ControlPlaneError(422, "EMPTY_CLUSTER", "至少需要一个 workcell")
        if len(ids) != len(set(ids)):
            raise ControlPlaneError(422, "DUPLICATE_WORKCELL", "workcell id 重复")
        known = set(ids)
        for link in cluster.links:
            if link.from_cell not in known or link.to_cell not in known:
                raise ControlPlaneError(422, "BAD_LINK", "链路引用了未知 workcell")
            if link.from_cell == link.to_cell:
                raise ControlPlaneError(422, "BAD_LINK", "链路不能指向自身")
        return cluster

    def _require_protocol(self, name: str) -> ProtocolMapping:
        try:
            return self._protocols[name]
        except KeyError:
            raise ControlPlaneError(404, "PROTOCOL_NOT_FOUND", f"未登记协议：{name}") from None

    def _require_workcell(self, workcell_id: str) -> Workcell:
        if self._cluster is None:
            raise ControlPlaneError(409, "NO_CLUSTER", "尚未加载集群拓扑")
        for cell in self._cluster.workcells:
            if cell.id == workcell_id:
                return cell
        raise ControlPlaneError(404, "WORKCELL_NOT_FOUND", f"未知 workcell：{workcell_id}")

    def _find_link(self, from_cell: str, to_cell: str) -> CellLink | None:
        if self._cluster is None:
            return None
        for link in self._cluster.links:
            if link.from_cell == from_cell and link.to_cell == to_cell:
                return link
        return None

    def _track(self, coro: Any) -> None:
        job = asyncio.create_task(coro)
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload, "at": utcnow().isoformat()}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("drop event %s: subscriber queue full", event_type)
