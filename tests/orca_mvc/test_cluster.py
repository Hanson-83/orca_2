"""双 workcell 拓扑与跨 cell 转运占位。"""

from __future__ import annotations

import asyncio
import time

import httpx


async def test_bundled_cluster_has_two_workcells(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/cluster")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "cluster_demo"
    assert len(body["workcells"]) == 2
    assert {cell["id"] for cell in body["workcells"]} == {"cell_a", "cell_b"}
    assert body["links"][0]["link_type"] == "translator"
    assert body["links"][0]["supports_deadlock_parking"] is False


async def test_load_json_and_transfer_arrives(client: httpx.AsyncClient) -> None:
    payload = {
        "id": "lab_pair",
        "workcells": [
            {"id": "west", "name": "西区", "devices": ["lh"], "transporters": ["arm"], "status": "idle"},
            {"id": "east", "name": "东区", "devices": ["reader"], "transporters": ["arm"], "status": "fault"},
        ],
        "links": [
            {
                "from_cell": "west",
                "to_cell": "east",
                "link_type": "placeholder",
                "link_id": "window",
                "supports_deadlock_parking": False,
            }
        ],
    }
    loaded = await client.post("/api/v1/cluster/load", json=payload)
    assert loaded.status_code == 200, loaded.text
    view = loaded.json()
    assert len(view["workcells"]) == 2
    by_id = {cell["id"]: cell for cell in view["workcells"]}
    assert by_id["east"]["status"] == "fault"

    missing = await client.post(
        "/api/v1/cluster/transfers",
        json={"labware_id": "plate-1", "from_cell": "east", "to_cell": "west"},
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "NO_LINK"

    created = await client.post(
        "/api/v1/cluster/transfers",
        json={"labware_id": "plate-demo", "from_cell": "west", "to_cell": "east"},
    )
    assert created.status_code == 201, created.text
    transfer_id = created.json()["transfer_id"]
    assert created.json()["state"] == "requested"

    deadline = time.monotonic() + 3
    state = created.json()["state"]
    while time.monotonic() < deadline:
        rows = (await client.get("/api/v1/cluster/transfers")).json()
        match = next(row for row in rows if row["transfer_id"] == transfer_id)
        state = match["state"]
        if state == "arrived":
            break
        await asyncio.sleep(0.02)
    assert state == "arrived"


async def test_reject_link_to_unknown_cell(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/cluster/load",
        json={
            "id": "broken",
            "workcells": [{"id": "only", "name": "only", "status": "idle"}],
            "links": [{"from_cell": "only", "to_cell": "missing", "link_type": "placeholder"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "BAD_LINK"
