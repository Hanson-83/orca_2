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
    if host not in {"127.0.0.1", "localhost", "::1"}:
        logging.getLogger("orca_mvc.api").warning(
            "控制面没有认证，绑定 %s 会把任务接口暴露到该地址",
            host,
        )
    uvicorn.run(
        "orca_mvc.api.app:app",
        host=host,
        port=port,
        log_level="info",
        factory=False,
    )


if __name__ == "__main__":
    main()
