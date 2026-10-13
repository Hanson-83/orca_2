"""`python -m orca_mvc.api` 启动控制面。"""

from __future__ import annotations

import logging
import os

import uvicorn


def main() -> None:
    host = os.environ.get("ORCA_MVC_HOST", "127.0.0.1")
    port = int(os.environ.get("ORCA_MVC_PORT", "8100"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    token = os.environ.get("ORCA_MVC_API_TOKEN", "").strip()
    log = logging.getLogger("orca_mvc.api")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        if not token:
            log.error("绑定 %s 需要 ORCA_MVC_API_TOKEN。拒绝启动。", host)
            raise SystemExit(2)
        os.environ["ORCA_MVC_AUTH"] = os.environ.get("ORCA_MVC_AUTH", "required")
        log.warning("控制面绑定 %s，已要求 Bearer 令牌", host)
    elif not token:
        log.warning("未设置 ORCA_MVC_API_TOKEN，控制面在本机开放。不要改绑定地址。")
    uvicorn.run(
        "orca_mvc.api.app:app",
        host=host,
        port=port,
        log_level="info",
        factory=False,
    )


if __name__ == "__main__":
    main()
