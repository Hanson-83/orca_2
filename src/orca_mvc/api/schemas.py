"""HTTP 请求体。响应直接复用领域模型。"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from orca_mvc.models.enums import RunMode


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    protocol_ref: str = Field(min_length=1)
    workcell_id: str = Field(min_length=1)
    run_mode: RunMode = RunMode.MOCK
    params: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class TransferRequest(BaseModel):
    labware_id: str = Field(min_length=1)
    from_cell: str = Field(min_length=1)
    to_cell: str = Field(min_length=1)


class Sila2CallRequest(BaseModel):
    feature: str = Field(min_length=1)
    command: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class Ros2CallRequest(BaseModel):
    kind: Literal["service", "publish"] = "service"
    service: str | None = None
    topic: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
