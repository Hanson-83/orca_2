"""控制面枚举。取值与设计规格里的状态字面量一致。"""

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunMode(str, Enum):
    """控制面运行模式。

    MOCK 只存在于本控制面。Orca daemon 的 wire 值是 PURE_SIM / DEVICE_SIM / LIVE。
    OrcaDaemonBackend 把 MOCK 显式映射成 PURE_SIM，不会原样塞进 POST /executions。
    """

    PURE_SIM = "PURE_SIM"
    DEVICE_SIM = "DEVICE_SIM"
    LIVE = "LIVE"
    MOCK = "MOCK"


class WorkcellStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    FAULT = "fault"
    OFFLINE = "offline"


class LinkType(str, Enum):
    TRANSLATOR = "translator"
    HUMAN_WINDOW = "human_window"
    PLACEHOLDER = "placeholder"


class TransferState(str, Enum):
    REQUESTED = "requested"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    FAILED = "failed"
