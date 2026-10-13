"""用 httpx.MockTransport 测 daemon 客户端，不启动 orca 进程。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from orca_mvc.api.app import create_app
from orca_mvc.models.enums import RunMode
from orca_mvc.models.task import ExperimentTask
from orca_mvc.runtime.daemon_backend import (
    DaemonRequestError,
    DaemonVariableError,
    OrcaDaemonBackend,
    map_daemon_status,
)
from orca_mvc.services.control_plane import ControlPlane


def _task(**overrides: object) -> ExperimentTask:
    now = datetime.now(timezone.utc)
    payload = {
        "id": "task-1",
        "name": "读板",
        "protocol_ref": "plate_readout",
        "workcell_id": "cell_a",
        "run_mode": RunMode.MOCK,
        "params": {"cycles": 2, "note": "a"},
        "created_at": now,
        "updated_at": now,
        "mapping": {"workflow_template_name": "plate_readout"},
    }
    payload.update(overrides)
    return ExperimentTask.model_validate(payload)


class _DaemonScript:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.phase = "accepting"
        self.missing = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body: object
        if request.content:
            body = json.loads(request.content.decode())
        else:
            body = None
        self.calls.append((request.method, request.url.path, body))
        path = request.url.path
        if path == "/health":
            return httpx.Response(200, json={"daemon": "ok", "system_loaded": True, "sim": True})
        if path == "/executions":
            assert isinstance(body, dict)
            assert body["run_mode"] == "PURE_SIM"
            assert body["workflow_name"] == "plate_readout"
            assert body["acknowledge_warnings"] is False
            assert body["variables"] == {"cycles": 2, "note": "a"}
            assert "MOCK" not in json.dumps(body)
            return httpx.Response(
                200,
                json={
                    "id": "exec-9",
                    "workflow_name": "plate_readout",
                    "status": "running",
                    "error": None,
                    "paused": False,
                },
            )
        if path == "/operations/get-execution":
            if self.missing:
                return httpx.Response(404, json={"detail": "execution 'exec-missing' not found"})
            return httpx.Response(
                200,
                json={
                    "execution": {
                        "id": "exec-9",
                        "workflow_name": "plate_readout",
                        "status": self.phase,
                        "error": None,
                        "paused": False,
                        "abort_armed": False,
                    }
                },
            )
        if path == "/operations/list-executions":
            return httpx.Response(
                200,
                json={
                    "executions": [
                        {
                            "id": "exec-9",
                            "workflow_name": "plate_readout",
                            "status": self.phase,
                        }
                    ]
                },
            )
        if path == "/operations/stop-execution":
            assert isinstance(body, dict)
            if body["confirm"] is False:
                return httpx.Response(
                    200,
                    json={
                        "status": "armed",
                        "execution_id": body["execution_id"],
                        "phase": "accepting",
                        "message": "armed",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "status": "aborted",
                    "execution_id": body["execution_id"],
                    "phase": "aborted",
                    "message": "aborted",
                },
            )
        return httpx.Response(500, json={"detail": f"unexpected {path}"})


def _backend(script: _DaemonScript) -> OrcaDaemonBackend:
    return OrcaDaemonBackend("http://127.0.0.1:51293", transport=httpx.MockTransport(script))


async def test_submit_maps_mock_to_pure_sim_and_reads_phase() -> None:
    script = _DaemonScript()
    backend = _backend(script)
    try:
        ref = await backend.submit(_task())
        assert ref == "exec-9"
        assert await backend.get_execution_status(ref) == "running"
        script.phase = "completed"
        assert await backend.get_execution_status(ref) == "completed"
        rows = await backend.list_executions()
        assert rows[0]["id"] == "exec-9"
        url, ok = await backend.daemon_health()
        assert url == "http://127.0.0.1:51293"
        assert ok is True
    finally:
        await backend.aclose()


async def test_cancel_is_two_step_confirm() -> None:
    script = _DaemonScript()
    backend = _backend(script)
    try:
        await backend.cancel("exec-9")
    finally:
        await backend.aclose()
    stops = [call for call in script.calls if call[1] == "/operations/stop-execution"]
    assert stops[0][2] == {"execution_id": "exec-9", "confirm": False}
    assert stops[1][2] == {"execution_id": "exec-9", "confirm": True}


async def test_missing_execution_is_key_error() -> None:
    script = _DaemonScript()
    script.missing = True
    backend = _backend(script)
    try:
        with pytest.raises(KeyError):
            await backend.get_execution_status("exec-missing")
    finally:
        await backend.aclose()


def test_status_vocabulary() -> None:
    assert map_daemon_status("accepting") == "running"
    assert map_daemon_status("draining") == "running"
    assert map_daemon_status("stopping") == "running"
    assert map_daemon_status("aborted") == "cancelled"
    assert map_daemon_status("failed") == "failed"


async def test_nested_params_are_rejected_before_http() -> None:
    script = _DaemonScript()
    backend = _backend(script)
    try:
        with pytest.raises(DaemonVariableError):
            await backend.submit(_task(params={"plate": {"id": 1}}))
    finally:
        await backend.aclose()
    assert script.calls == []


async def test_http_error_is_daemon_request_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"detail": {"code": "not_found", "message": "workflow missing", "extras": {}}},
        )

    backend = OrcaDaemonBackend("http://127.0.0.1:1", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(DaemonRequestError, match="workflow missing") as caught:
            await backend.submit(_task())
        assert caught.value.status_code == 404
    finally:
        await backend.aclose()


async def test_control_plane_submit_uses_daemon_client() -> None:
    script = _DaemonScript()
    script.phase = "completed"
    plane = ControlPlane(
        backend=_backend(script),
        poll_interval=0.01,
    )
    await plane.startup()
    try:
        app = create_app(plane)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/api/v1/health")
            assert health.json()["runtime_backend"] == "orca-daemon"
            assert health.json()["daemon_reachable"] is True
            assert health.json()["daemon_url"] == "http://127.0.0.1:51293"
            created = await client.post(
                "/api/v1/tasks",
                json={
                    "name": "交给 daemon",
                    "protocol_ref": "plate_readout",
                    "workcell_id": "cell_a",
                    "run_mode": "MOCK",
                    "params": {"cycles": 2, "note": "a"},
                },
            )
            assert created.status_code == 201, created.text
            task_id = created.json()["id"]
            submitted = await client.post(f"/api/v1/tasks/{task_id}/submit")
            assert submitted.status_code == 200, submitted.text
            body = submitted.json()
            assert body["execution_ref"] == "exec-9"
            assert body["mapping"]["orca_submit"]["phase"] == "submitted"
            assert body["mapping"]["orca_submit"]["wire_run_mode"] == "PURE_SIM"
            stored = body
            for _ in range(50):
                stored = (await client.get(f"/api/v1/tasks/{task_id}")).json()
                if stored["status"] == "completed":
                    break
            assert stored["status"] == "completed"
    finally:
        await plane.shutdown()
