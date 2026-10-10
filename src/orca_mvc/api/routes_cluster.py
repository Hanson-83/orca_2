"""集群拓扑与跨 cell 转运占位。"""

from typing import Any

from fastapi import APIRouter, Depends

from orca_mvc.api.deps import get_plane
from orca_mvc.api.schemas import TransferRequest
from orca_mvc.models.cluster import ClusterView, Transfer
from orca_mvc.services.control_plane import ControlPlane

router = APIRouter(tags=["cluster"])


@router.get("/cluster", response_model=ClusterView)
def get_cluster(plane: ControlPlane = Depends(get_plane)) -> ClusterView:
    return plane.get_cluster()


@router.post("/cluster/load", response_model=ClusterView)
def load_cluster(
    body: dict[str, Any],
    plane: ControlPlane = Depends(get_plane),
) -> ClusterView:
    return plane.load_cluster(body)


@router.get("/cluster/transfers", response_model=list[Transfer])
def list_transfers(plane: ControlPlane = Depends(get_plane)) -> list[Transfer]:
    return plane.list_transfers()


@router.post("/cluster/transfers", response_model=Transfer, status_code=201)
async def request_transfer(
    body: TransferRequest,
    plane: ControlPlane = Depends(get_plane),
) -> Transfer:
    return await plane.request_transfer(
        labware_id=body.labware_id,
        from_cell=body.from_cell,
        to_cell=body.to_cell,
    )
