"""FastAPI 控制面。默认只给本机用。令牌可选，见 orca_mvc.auth。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
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
_AUTH_EXEMPT = {
    f"{API_PREFIX}/health",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/favicon.ico",
}


def _cors_origins() -> list[str]:
    raw = os.environ.get("ORCA_MVC_CORS_ORIGINS", "")
    if not raw.strip():
        return list(_DEFAULT_ORIGINS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def require_auth(request: Request) -> None:
    """受保护路由校验 Bearer。健康检查和文档页放行。"""

    if request.method == "OPTIONS":
        return
    path = request.url.path
    if path in _AUTH_EXEMPT or path.startswith("/docs"):
        return
    policy = request.app.state.auth
    query_token = request.query_params.get("token") if path == f"{API_PREFIX}/events" else None
    allowed, message = policy.allows(request.headers.get("authorization"), query_token)
    if allowed:
        return
    raise HTTPException(
        status_code=401,
        detail={"code": "UNAUTHORIZED", "message": message, "retryable": False},
    )


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
            "Orca MVC 控制面（Phase 2）。默认绑定 127.0.0.1。"
            "未设置 ORCA_MVC_API_TOKEN 时本机开放并打警告；"
            "设置令牌、ORCA_MVC_AUTH=required，或绑定非回环地址时要求 Bearer。"
            "执行面默认是 MockRuntimeBackend。ORCA_MVC_RUNTIME=daemon 时"
            "按 daemon_backend 里核对过的路由访问本机 Orca daemon。"
            "不要把这个服务暴露到公网。"
        ),
        lifespan=lifespan,
        dependencies=[Depends(require_auth)],
    )
    app.state.plane = plane
    app.state.auth = plane.auth
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type"],
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
    async def health() -> dict[str, Any]:
        daemon_url, reachable = await plane.daemon_probe()
        body: dict[str, Any] = {
            "status": "ok",
            "service": "orca-mvc",
            "version": __version__,
            "runtime": plane.runtime_name,
            "runtime_backend": plane.runtime_name,
            "daemon_reachable": reachable,
            "daemon_url": daemon_url,
        }
        body.update(plane.auth.health_fields())
        return body

    return app


app = create_app()
