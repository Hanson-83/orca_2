"""进程内 SiLA2 形状的 HTTP stub。不是认证过的 SiLA2 gRPC 服务器，也不连设备。

线协议只覆盖联调需要的子集，字段名对齐 SiLA2 概念：

- ``GET /sila/v1/features``
- ``POST /sila/v1/features/{featureIdentifier}/commands/{commandIdentifier}``
  请求 ``{"parameters": {...}}``
  成功 ``commandExecutionUUID`` + ``executionStatus=finishedSuccessfully``
  未知 Feature / Command 返回 ``errorType=DefinedExecutionError``

``python -m orca_mvc.adapters.sila2_stub`` 在 ``127.0.0.1:8110`` 拉起，供手工联调。
控制面默认不绑端口，用 httpx ASGITransport 打同一张路由表。
"""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

FEATURE_CATALOG: dict[str, tuple[str, ...]] = {
    "ShakerControl": ("Shake", "Stop"),
    "SealControl": ("Seal",),
    "PlateReader": ("Read",),
}


def create_sila2_stub_app() -> FastAPI:
    app = FastAPI(
        title="orca-mvc-sila2-stub",
        description="SiLA2 形状的本地 HTTP stub。mode 应标成 sim，不是实机。",
    )

    @app.get("/sila/v1/features")
    def list_features() -> dict[str, Any]:
        features = [
            {"featureIdentifier": name, "commands": list(commands)}
            for name, commands in FEATURE_CATALOG.items()
        ]
        return {"features": features}

    @app.post("/sila/v1/features/{feature}/commands/{command}")
    async def run_command(feature: str, command: str, request: Request) -> JSONResponse:
        parameters, error = await _parameters(request)
        if error is not None:
            return error
        if feature not in FEATURE_CATALOG:
            return _defined_error(
                404,
                "UnknownFeature",
                f"unknown feature: {feature}",
            )
        if command not in FEATURE_CATALOG[feature]:
            return _defined_error(
                404,
                "UnknownCommand",
                f"unknown command: {feature}/{command}",
            )
        return JSONResponse(
            {
                "commandExecutionUUID": uuid4().hex,
                "executionStatus": "finishedSuccessfully",
                "response": {"result": "ok", "parameters": parameters},
            }
        )

    return app


async def _parameters(request: Request) -> tuple[dict[str, Any], JSONResponse | None]:
    raw = await request.body()
    if not raw:
        return {}, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}, _defined_error(400, "InvalidCommand", "body is not JSON")
    if not isinstance(payload, dict):
        return {}, _defined_error(400, "InvalidCommand", "body must be an object")
    parameters = payload.get("parameters", {})
    if not isinstance(parameters, dict):
        return {}, _defined_error(400, "InvalidCommand", "parameters must be an object")
    return parameters, None


def _defined_error(status_code: int, identifier: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "errorType": "DefinedExecutionError",
            "errorIdentifier": identifier,
            "message": message,
        },
    )


def main() -> None:
    import uvicorn

    host = os.environ.get("ORCA_MVC_SILA2_HOST", "127.0.0.1")
    port = int(os.environ.get("ORCA_MVC_SILA2_PORT", "8110"))
    uvicorn.run(create_sila2_stub_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
