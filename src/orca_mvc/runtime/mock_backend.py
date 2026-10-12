"""用时间线模拟 Orca 执行，不接触 SystemRuntime。"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from orca_mvc.models.task import ExperimentTask

logger = logging.getLogger("orca_mvc.runtime.mock")


class MockRuntimeBackend:
    """submit 之后按 queued → running → completed 推进。

    两个时间参数故意分开：step_delay 是进入 running 前的排队，
    running_hold 让多条任务有一段重叠的 running，便于并行验收。
    """

    name = "mock"

    def __init__(self, *, step_delay: float = 0.2, running_hold: float = 0.6) -> None:
        self._step_delay = step_delay
        self._running_hold = running_hold
        self._status: dict[str, str] = {}
        self._records: dict[str, dict[str, object]] = {}
        self._cancelled: set[str] = set()
        self._jobs: set[asyncio.Task[None]] = set()

    async def submit(self, task: ExperimentTask) -> str:
        ref = f"mock-{uuid4().hex[:12]}"
        mapping = task.mapping or {}
        self._status[ref] = "queued"
        self._records[ref] = {
            "task_id": task.id,
            "protocol_ref": task.protocol_ref,
            "workflow_template_name": mapping.get("workflow_template_name"),
            "run_mode": task.run_mode.value,
            "simulated": True,
        }
        job = asyncio.create_task(self._timeline(ref), name=f"mock-{ref}")
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)
        logger.info("mock submit task=%s execution_ref=%s", task.id, ref)
        return ref

    async def get_execution_status(self, execution_ref: str) -> str:
        try:
            return self._status[execution_ref]
        except KeyError:
            raise KeyError(execution_ref) from None

    async def cancel(self, execution_ref: str) -> None:
        if execution_ref not in self._status:
            raise KeyError(execution_ref)
        self._cancelled.add(execution_ref)
        if self._status[execution_ref] not in {"completed", "failed", "cancelled"}:
            self._status[execution_ref] = "cancelled"
        logger.info("mock cancel execution_ref=%s", execution_ref)

    async def aclose(self) -> None:
        jobs = list(self._jobs)
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)

    async def _timeline(self, ref: str) -> None:
        if not await self._wait(ref, self._step_delay):
            return
        self._status[ref] = "running"
        if not await self._wait(ref, self._running_hold):
            return
        self._status[ref] = "completed"
        logger.info("mock completed execution_ref=%s", ref)

    async def _wait(self, ref: str, seconds: float) -> bool:
        """等到时间耗尽。期间若被取消，把状态写成 cancelled 并返回 False。"""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while True:
            if ref in self._cancelled:
                self._status[ref] = "cancelled"
                return False
            remaining = deadline - loop.time()
            if remaining <= 0:
                return ref not in self._cancelled
            await asyncio.sleep(min(0.02, remaining))
