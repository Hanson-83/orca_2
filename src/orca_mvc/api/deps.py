"""从请求里取出控制面实例。"""

from fastapi import Request

from orca_mvc.services.control_plane import ControlPlane


def get_plane(request: Request) -> ControlPlane:
    return request.app.state.plane
