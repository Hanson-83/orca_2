"""RuntimeBackend：控制面看见的执行面。"""

from typing import Protocol

from orca_mvc.models.task import ExperimentTask


class RuntimeBackend(Protocol):
    """submit 返回 execution_ref。状态字面量与 TaskStatus 对齐。"""

    name: str

    async def submit(self, task: ExperimentTask) -> str:
        """提交一条任务，返回 execution_ref。"""

    async def get_execution_status(self, execution_ref: str) -> str:
        """返回 pending/queued/running/completed/failed/cancelled 之一。"""

    async def cancel(self, execution_ref: str) -> None:
        """请求取消。找不到 execution_ref 时抛出 KeyError。"""
