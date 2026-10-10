"""ExperimentTask：控制面一次实验提交。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from orca_mvc.models.enums import RunMode, TaskStatus


class ExperimentTask(BaseModel):
    """一条实验任务。

    protocol_ref 对应预注册的 ProtocolMapping.name，再映射到
    Orca WorkflowTemplate.name。Phase 1 的 execution_ref 来自 MockRuntimeBackend，
    不会发给 SystemRuntime。
    """

    id: str
    name: str
    protocol_ref: str
    workcell_id: str
    run_mode: RunMode = RunMode.MOCK
    params: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    execution_ref: str | None = None
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    mapping: dict[str, Any] | None = None
