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
            "未安装 MCP SDK。执行：python -m pip install 'mcp>=1.9,<3'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    try:
        server = build_server(api_url)
    except ModuleNotFoundError:
        print(
            "未安装 MCP SDK。执行：python -m pip install 'mcp>=1.9,<3'",
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
        if host not in {"127.0.0.1", "localhost", "::1"}:
            logging.getLogger("orca_mvc.mcp").warning(
                "MCP 没有认证，绑定 %s 会把工具暴露到该地址",
                host,
            )
        server.run("streamable-http", host=host, port=port)
        return
    print(f"未知 ORCA_MVC_MCP_TRANSPORT={transport!r}，只用 stdio 或 streamable-http", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
