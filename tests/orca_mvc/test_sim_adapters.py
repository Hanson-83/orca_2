"""SiLA2 HTTP stub 与 ROS2 总线。不需要机器人，也不需要 rclpy。"""

from __future__ import annotations

import httpx
import pytest

from orca_mvc.adapters.base import AdapterOffline, UnknownSilaCommand, UnknownSilaFeature
from orca_mvc.adapters.ros2_sim import Ros2SimAdapter
from orca_mvc.adapters.sila2_sim import Sila2SimAdapter
from orca_mvc.adapters.sila2_stub import create_sila2_stub_app


async def test_sila2_stub_command_shape() -> None:
    app = create_sila2_stub_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://sila2.stub") as client:
        listed = await client.get("/sila/v1/features")
        assert listed.status_code == 200
        names = {item["featureIdentifier"] for item in listed.json()["features"]}
        assert "ShakerControl" in names
        called = await client.post(
            "/sila/v1/features/ShakerControl/commands/Shake",
            json={"parameters": {"rpm": 200}},
        )
        assert called.status_code == 200, called.text
        body = called.json()
        assert body["executionStatus"] == "finishedSuccessfully"
        assert body["commandExecutionUUID"]
        missing = await client.post(
            "/sila/v1/features/NotAFeature/commands/Do",
            json={"parameters": {}},
        )
        assert missing.status_code == 404
        assert missing.json()["errorIdentifier"] == "UnknownFeature"
        unknown_cmd = await client.post(
            "/sila/v1/features/ShakerControl/commands/Nope",
            json={"parameters": {}},
        )
        assert unknown_cmd.json()["errorIdentifier"] == "UnknownCommand"


async def test_sila2_sim_adapter_talks_to_stub() -> None:
    adapter = Sila2SimAdapter()
    assert adapter.health()["mode"] == "sim"
    with pytest.raises(AdapterOffline):
        await adapter.call_command("ShakerControl", "Shake", {})
    await adapter.connect()
    try:
        features = await adapter.list_features()
        assert "PlateReader" in features
        result = await adapter.call_command("SealControl", "Seal", {"temp": 170})
        assert result["mode"] == "sim"
        assert result["simulated"] is True
        assert result["executionStatus"] == "finishedSuccessfully"
        assert result["transport"] == "http-stub"
        with pytest.raises(UnknownSilaFeature):
            await adapter.call_command("NotAFeature", "Do", {})
        with pytest.raises(UnknownSilaCommand):
            await adapter.call_command("ShakerControl", "Nope", {})
        assert adapter.health()["call_count"] == 1
    finally:
        await adapter.disconnect()


async def test_ros2_sim_replays_trace_and_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, dict]] = []

    def boom(topic: str, message: dict) -> None:
        seen.append((topic, message))
        raise RuntimeError("no rmw")

    monkeypatch.setenv("ORCA_MVC_ROS2", "rclpy")
    adapter = Ros2SimAdapter(rclpy_publish=boom)
    await adapter.connect()
    assert adapter.health()["mode"] == "sim"
    assert adapter.health()["recorded_count"] == 2
    topics = await adapter.list_topics()
    assert "/workcell/arm/state" in topics
    await adapter.publish("/workcell/arm/cmd", {"target": "home"})
    assert seen[0][0] == "/workcell/arm/cmd"
    assert adapter.health()["rclpy"] == "degraded"
    assert adapter.health()["backend"] == "message-bus"
    service = await adapter.call_service("/workcell/arm/move", {"target": "deck"})
    assert service["result"] == "ok"
    assert service["response"]["success"] is True
    assert service["type"] == "orca_mvc/Trigger"


async def test_ros2_sim_marks_rclpy_active_without_claiming_hardware() -> None:
    adapter = Ros2SimAdapter(rclpy_publish=lambda _topic, _message: None)
    await adapter.connect()
    await adapter.publish("/workcell/arm/cmd", {"target": "home"})
    health = adapter.health()
    assert health["mode"] == "sim"
    assert health["rclpy"] == "active"
    assert health["backend"] == "message-bus+rclpy"
