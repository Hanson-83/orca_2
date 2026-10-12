"""SiLA2 / ROS2 mock 的健康检查与模拟调用。"""

from typing import Any

from fastapi import APIRouter, Depends

from orca_mvc.api.deps import get_plane
from orca_mvc.api.schemas import Ros2CallRequest, Sila2CallRequest
from orca_mvc.services.control_plane import ControlPlane

router = APIRouter(tags=["adapters"])


@router.get("/adapters")
def adapter_health(plane: ControlPlane = Depends(get_plane)) -> dict[str, Any]:
    return plane.adapter_health()


@router.post("/adapters/sila2/call")
async def call_sila2(
    body: Sila2CallRequest,
    plane: ControlPlane = Depends(get_plane),
) -> dict[str, Any]:
    return await plane.call_sila2(body.feature, body.command, body.params)


@router.post("/adapters/ros2/call")
async def call_ros2(
    body: Ros2CallRequest,
    plane: ControlPlane = Depends(get_plane),
) -> dict[str, Any]:
    return await plane.call_ros2(
        kind=body.kind,
        service=body.service,
        topic=body.topic,
        payload=body.payload,
    )
