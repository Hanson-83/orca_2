"""daemon 骨架只引用源码里存在的路由，并且拒绝在 Phase 1 发出请求。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from orca_mvc.models.enums import RunMode
from orca_mvc.models.task import ExperimentTask
from orca_mvc.runtime.daemon_backend import (
    DAEMON_ROUTE_CATALOG,
    DAEMON_RUN_MODES,
    DaemonNotWired,
    OrcaDaemonBackend,
)

_ROOT = Path(__file__).resolve().parents[2]


def _task() -> ExperimentTask:
    now = datetime.now(timezone.utc)
    return ExperimentTask(
        id="task-daemon",
        name="不应发出",
        protocol_ref="plate_readout",
        workcell_id="cell_a",
        run_mode=RunMode.MOCK,
        created_at=now,
        updated_at=now,
    )


def test_catalog_paths_exist_in_daemon_source() -> None:
    routes = (_ROOT / "src/orca/daemon/routes.py").read_text(encoding="utf-8")
    operations = (_ROOT / "src/orca/daemon/operations_router.py").read_text(encoding="utf-8")
    lifecycle = (_ROOT / "src/orca/daemon/lifecycle.py").read_text(encoding="utf-8")
    entry = (_ROOT / "src/orca/daemon/__main__.py").read_text(encoding="utf-8")

    assert DAEMON_ROUTE_CATALOG["submit_workflow"] == ("POST", "/executions")
    assert '@router.post("/executions"' in routes
    for key in ("list_executions", "get_execution", "get_execution_detail", "stop_execution", "remove_execution"):
        _method, path = DAEMON_ROUTE_CATALOG[key]
        assert f'path="{path}"' in operations
    assert "daemon.json" in lifecycle
    assert 'host="127.0.0.1"' in entry
    assert DAEMON_RUN_MODES == ("PURE_SIM", "DEVICE_SIM", "LIVE")
    assert "MOCK" not in DAEMON_RUN_MODES


async def test_daemon_backend_does_not_call_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCA_DAEMON_URL", raising=False)
    backend = OrcaDaemonBackend()
    assert backend.base_url is None
    with pytest.raises(DaemonNotWired, match="/executions"):
        await backend.submit(_task())
    with pytest.raises(DaemonNotWired, match="/operations/get-execution"):
        await backend.get_execution_status("exec-1")
    with pytest.raises(DaemonNotWired, match="/operations/stop-execution"):
        await backend.cancel("exec-1")
