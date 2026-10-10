"""Workcell、集群拓扑与跨 cell 转运占位。"""

from datetime import datetime

from pydantic import BaseModel, Field

from orca_mvc.models.enums import LinkType, TransferState, WorkcellStatus


class Workcell(BaseModel):
    id: str
    name: str
    devices: list[str] = Field(default_factory=list)
    transporters: list[str] = Field(default_factory=list)
    status: WorkcellStatus = WorkcellStatus.IDLE
    topology_ref: str | None = None


class CellLink(BaseModel):
    from_cell: str
    to_cell: str
    link_type: LinkType
    link_id: str | None = None
    supports_deadlock_parking: bool = False


class Cluster(BaseModel):
    id: str
    workcells: list[Workcell]
    links: list[CellLink] = Field(default_factory=list)


class Transfer(BaseModel):
    """跨 cell 转运占位。Phase 1 只推进状态，不调用 Orca Translator。"""

    transfer_id: str
    labware_id: str
    from_cell: str
    to_cell: str
    state: TransferState
    created_at: datetime
    updated_at: datetime


class ClusterView(BaseModel):
    """查询视图。workcell.status 里的 idle/busy 按当前任务推导，fault/offline 保持拓扑原值。"""

    id: str
    workcells: list[Workcell]
    links: list[CellLink]
    transfers: list[Transfer] = Field(default_factory=list)
