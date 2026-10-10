"""FastAPI 控制面。默认只给本机用，没有认证。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from orca_mvc import __version__
from orca_mvc.api.routes_adapters import router as adapters_router
from orca_mvc.api.routes_cluster import router as cluster_router
from orca_mvc.api.routes_events import router as events_router
from orca_mvc.api.routes_tasks import router as tasks_router
from orca_mvc.services.control_plane import ControlPlane, ControlPlaneError

logger = logging.getLogger("orca_mvc.api")

API_PREFIX = "/api/v1"
_DEFAULT_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")


def _cors_origins() -> list[str]:
    raw = os.environ.get("ORCA_MVC_CORS_ORIGINS", "")
    if not raw.strip():
        return list(_DEFAULT_ORIGINS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def create_app(plane: ControlPlane | None = None) -> FastAPI:
    """构建应用。传入 plane 时由调用方负责 startup；否则在 lifespan 里启动。"""

    owned = plane is None
    plane = plane or ControlPlane.from_env()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if owned:
            await plane.startup()
        try:
            yield
        finally:
            if owned:
                await plane.shutdown()

    app = FastAPI(
        title="orca-mvc",
        version=__version__,
        description=(
            "Orca MVC 控制面（Phase 1）。默认绑定 127.0.0.1，没有认证。"
            "不要把这个服务暴露到公网或局域网。"
            "执行面默认是 MockRuntimeBackend；真实 daemon 路由见 "
            "orca_mvc.runtime.daemon_backend，Phase 2 才调用。"
        ),
        lifespan=lifespan,
    )
    app.state.plane = plane
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(ControlPlaneError)
    async def _control_plane_error(_request: Request, exc: ControlPlaneError) -> JSONResponse:
        logger.info("api error code=%s status=%s", exc.code, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                }
            },
        )

    router_kw = {"prefix": API_PREFIX}
    app.include_router(tasks_router, **router_kw)
    app.include_router(cluster_router, **router_kw)
    app.include_router(adapters_router, **router_kw)
    app.include_router(events_router, **router_kw)

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "orca-mvc",
            "version": __version__,
            "runtime": plane.runtime_name,
            "auth": "none",
        }

    return app


app = create_app()
