# 经验教训

## 2026-10-10 Orca MVC Phase 1

### 仓库测试入口会拉起整套引擎

`tests/conftest.py` 在收集阶段就 `import orca`。控制面测试不需要驱动栈。跑 `tests/orca_mvc` 时加 `--confcutdir=tests/orca_mvc`，否则没装 `cheshire-drivers` 的环境会在导入阶段失败。用例自己把 `src` 插进 `sys.path`。

### 不要给 daemon 编一个默认端口

`orca start` 把端口写进 `~/.orca/daemon.json`，进程只绑 `127.0.0.1`。设计稿里出现过 `8000`，源码里没有这个默认值。Phase 1 的 `OrcaDaemonBackend` 只在设置了 `ORCA_DAEMON_URL` 时记住地址，并且仍然不发请求。

### 路由以源码为准，并用测试锁住

执行相关读和停止不在 `GET /executions/{id}`。列表是 `GET /operations/list-executions`，详情是 `POST /operations/get-execution`，停止是 `POST /operations/stop-execution`（第一次 armed，`confirm=true` 才 abort）。`tests/orca_mvc/test_daemon_contract.py` 回读 daemon 源码，路径字符串消失时测试会失败。

### MCP SDK 2.x 改了入口

`mcp.server.fastmcp.FastMCP` 在 2.x 会直接报错。当前入口是 `mcp.server.mcpserver.MCPServer`，装饰器仍是 `@server.tool()`，默认 `run("stdio")`。不要为了旧教程把依赖钉死在 1.x，除非决定不跟 2.x。

### 控制面的 MOCK 不是 daemon 的 run_mode

daemon 只接受 `PURE_SIM`、`DEVICE_SIM`、`LIVE`。Phase 2 接线时要做显式映射，不能把 `MOCK` 原样放进 `POST /executions`。
