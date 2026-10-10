"""Server-Sent Events。浏览器优先用它刷新，断线再退回轮询。"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from orca_mvc.api.deps import get_plane
from orca_mvc.services.control_plane import ControlPlane

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(
    request: Request,
    plane: ControlPlane = Depends(get_plane),
) -> StreamingResponse:
    queue = plane.subscribe()

    async def stream():
        try:
            hello = json.dumps({"ok": True, "runtime": plane.runtime_name}, ensure_ascii=False)
            yield f"event: hello\ndata: {hello}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: {event['type']}\ndata: {payload}\n\n"
        finally:
            plane.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
