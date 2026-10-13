"""执行面适配。默认 Mock；``ORCA_MVC_RUNTIME=daemon`` 使用 HTTP 客户端。"""

from orca_mvc.runtime.base import RuntimeBackend
from orca_mvc.runtime.daemon_backend import (
    DAEMON_ROUTE_CATALOG,
    DAEMON_RUN_MODES,
    DaemonNotWired,
    DaemonRequestError,
    DaemonUnavailable,
    DaemonVariableError,
    OrcaDaemonBackend,
    map_control_run_mode,
    map_daemon_status,
    resolve_daemon_base_url,
)
from orca_mvc.runtime.mock_backend import MockRuntimeBackend

__all__ = [
    "DAEMON_ROUTE_CATALOG",
    "DAEMON_RUN_MODES",
    "DaemonNotWired",
    "DaemonRequestError",
    "DaemonUnavailable",
    "DaemonVariableError",
    "MockRuntimeBackend",
    "OrcaDaemonBackend",
    "RuntimeBackend",
    "map_control_run_mode",
    "map_daemon_status",
    "resolve_daemon_base_url",
]
