"""`python -m orca_mvc.mcp_server` 以 stdio 启动 MCP。"""

from __future__ import annotations

import logging
import os
import sys


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    api_url = os.environ.get("ORCA_MVC_API_URL", "http://127.0.0.1:8100")
    try:
        from orca_mvc.mcp_server.server import build_server
    except ModuleNotFoundError:
        print(
            "未安装 MCP SDK。执行：python -m pip install 'mcp>=2,<3'（或 pip install -e '.[mvc]'）",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    try:
        server = build_server(api_url)
    except ModuleNotFoundError:
        print(
            "未安装 MCP SDK。执行：python -m pip install 'mcp>=2,<3'（或 pip install -e '.[mvc]'）",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    transport = os.environ.get("ORCA_MVC_MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        server.run("stdio")
        return
    if transport == "streamable-http":
        host = os.environ.get("ORCA_MVC_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("ORCA_MVC_MCP_PORT", "8101"))
        token = os.environ.get("ORCA_MVC_API_TOKEN", "").strip()
        log = logging.getLogger("orca_mvc.mcp")
        if host not in {"127.0.0.1", "localhost", "::1"}:
            if not token:
                log.error("MCP HTTP 绑定 %s 需要 ORCA_MVC_API_TOKEN。拒绝启动。", host)
                raise SystemExit(2)
            log.warning(
                "MCP streamable-http 绑定 %s。控制面令牌会转发给 API；"
                "MCP 监听本身仍应只给本机，SDK 没有另做一层 OAuth。",
                host,
            )
        elif not token:
            log.warning("MCP 调用控制面时不带令牌。若 API 要求认证，工具会失败。")
        server.run("streamable-http", host=host, port=port)
        return
    print(f"未知 ORCA_MVC_MCP_TRANSPORT={transport!r}，只用 stdio 或 streamable-http", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
