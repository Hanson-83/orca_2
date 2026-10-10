"""内存中的任务表。单事件循环内再加一把锁，避免提交与状态回写交错。"""

from __future__ import annotations

import asyncio

from orca_mvc.models.enums import TaskStatus
from orca_mvc.models.task import ExperimentTask


class MemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, ExperimentTask] = {}
        self._lock = asyncio.Lock()

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    def get(self, task_id: str) -> ExperimentTask | None:
        task = self._tasks.get(task_id)
        return None if task is None else task.model_copy(deep=True)

    def require_live(self, task_id: str) -> ExperimentTask:
        """返回存储中的原对象，调用方必须已持有 lock。"""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    def insert(self, task: ExperimentTask) -> None:
        self._tasks[task.id] = task

    def list(self, status: TaskStatus | None = None) -> list[ExperimentTask]:
        rows = list(self._tasks.values())
        if status is not None:
            rows = [row for row in rows if row.status == status]
        rows.sort(key=lambda row: row.created_at)
        return [row.model_copy(deep=True) for row in rows]
