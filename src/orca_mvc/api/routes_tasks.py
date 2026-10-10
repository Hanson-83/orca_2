"""任务与协议路由。"""

from fastapi import APIRouter, Depends, Query

from orca_mvc.api.deps import get_plane
from orca_mvc.api.schemas import CreateTaskRequest
from orca_mvc.models.enums import TaskStatus
from orca_mvc.models.protocol import ProtocolMapping
from orca_mvc.models.task import ExperimentTask
from orca_mvc.services.control_plane import ControlPlane

router = APIRouter(tags=["tasks"])


@router.get("/protocols", response_model=list[ProtocolMapping])
def list_protocols(plane: ControlPlane = Depends(get_plane)) -> list[ProtocolMapping]:
    return plane.list_protocols()


@router.get("/tasks", response_model=list[ExperimentTask])
async def list_tasks(
    status: TaskStatus | None = Query(default=None),
    plane: ControlPlane = Depends(get_plane),
) -> list[ExperimentTask]:
    return await plane.list_tasks(status)


@router.post("/tasks", response_model=ExperimentTask, status_code=201)
async def create_task(
    body: CreateTaskRequest,
    plane: ControlPlane = Depends(get_plane),
) -> ExperimentTask:
    return await plane.create_task(
        name=body.name,
        protocol_ref=body.protocol_ref,
        workcell_id=body.workcell_id,
        run_mode=body.run_mode,
        params=body.params,
        priority=body.priority,
    )


@router.get("/tasks/{task_id}", response_model=ExperimentTask)
async def get_task(task_id: str, plane: ControlPlane = Depends(get_plane)) -> ExperimentTask:
    return await plane.get_task(task_id)


@router.post("/tasks/{task_id}/submit", response_model=ExperimentTask)
async def submit_task(task_id: str, plane: ControlPlane = Depends(get_plane)) -> ExperimentTask:
    return await plane.submit_task(task_id)


@router.post("/tasks/{task_id}/cancel", response_model=ExperimentTask)
async def cancel_task(task_id: str, plane: ControlPlane = Depends(get_plane)) -> ExperimentTask:
    return await plane.cancel_task(task_id)
