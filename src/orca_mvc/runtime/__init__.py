"""执行面适配。Phase 1 默认 Mock，daemon 客户端只留对照过源码的骨架。"""

from orca_mvc.runtime.base import RuntimeBackend
from orca_mvc.runtime.daemon_backend import (
    DAEMON_ROUTE_CATALOG,
    DAEMON_RUN_MODES,
    DaemonNotWired,
    OrcaDaemonBackend,
)
from orca_mvc.runtime.mock_backend import MockRuntimeBackend

__all__ = [
    "DAEMON_ROUTE_CATALOG",
    "DAEMON_RUN_MODES",
    "DaemonNotWired",
    "MockRuntimeBackend",
    "OrcaDaemonBackend",
    "RuntimeBackend",
]
