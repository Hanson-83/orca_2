"""SiLA2 / ROS2 mock：离线拒绝，在线调用写入日志。"""

from __future__ import annotations

import httpx
import pytest

from orca_mvc.adapters.base import AdapterOffline
from orca_mvc.adapters.ros2_mock import Ros2MockAdapter
from orca_mvc.adapters.sila2_mock import Sila2MockAdapter, UnknownSilaFeature


async def test_sila2_mock_health_and_call_log() -> None:
    adapter = Sila2MockAdapter()
    assert adapter.health()["status"] == "offline"
    assert adapter.health()["mode"] == "mock"
    with pytest.raises(AdapterOffline):
        await adapter.call_command("ShakerControl", "Shake", {})
    await adapter.connect()
    features = await adapter.list_features()
    assert "ShakerControl" in features
    result = await adapter.call_command("ShakerControl", "Shake", {"rpm": 300})
    assert result["simulated"] is True
    assert result["result"] == "ok"
    health = adapter.health()
    assert health["status"] == "online"
    assert health["call_count"] == 1
    assert health["recent_calls"][0]["command"] == "Shake"


async def test_unknown_sila_feature_is_rejected() -> None:
    adapter = Sila2MockAdapter()
    await adapter.connect()
    with pytest.raises(UnknownSilaFeature):
        await adapter.call_command("NotAFeature", "Do", {})
    assert adapter.health()["call_count"] == 0


async def test_unknown_sila_feature_http(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/adapters/sila2/call",
        json={"feature": "NotAFeature", "command": "Do", "params": {}},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_FEATURE"
    health = (await client.get("/api/v1/adapters")).json()
    assert health["sila2"]["call_count"] == 0


async def test_ros2_mock_publish_and_service() -> None:
    adapter = Ros2MockAdapter()
    with pytest.raises(AdapterOffline):
        await adapter.publish("/workcell/arm/cmd", {"x": 1})
    await adapter.connect()
    topics = await adapter.list_topics()
    assert "/workcell/arm/cmd" in topics
    await adapter.publish("/workcell/arm/cmd", {"x": 1})
    service = await adapter.call_service("/workcell/arm/move", {"target": "deck"})
    assert service["simulated"] is True
    health = adapter.health()
    assert health["call_count"] == 2
    assert {row["kind"] for row in health["recent_calls"]} == {"publish", "service"}


async def test_http_adapter_calls(client: httpx.AsyncClient) -> None:
    health = (await client.get("/api/v1/adapters")).json()
    assert health["sila2"]["status"] == "online"
    assert health["sila2"]["mode"] == "sim"
    assert health["sila2"]["transport"] == "http-stub"
    assert health["ros2"]["mode"] == "sim"
    assert health["ros2"]["backend"] == "message-bus"

    sila = await client.post(
        "/api/v1/adapters/sila2/call",
        json={"feature": "SealControl", "command": "Seal", "params": {"temp": 170}},
    )
    assert sila.status_code == 200, sila.text
    assert sila.json()["simulated"] is True

    ros = await client.post(
        "/api/v1/adapters/ros2/call",
        json={"kind": "service", "service": "/workcell/arm/move", "payload": {"pose": "home"}},
    )
    assert ros.status_code == 200, ros.text
    assert ros.json()["result"] == "ok"

    after = (await client.get("/api/v1/adapters")).json()
    assert after["sila2"]["call_count"] >= 1
    assert after["ros2"]["recent_calls"][-1]["service"] == "/workcell/arm/move"
