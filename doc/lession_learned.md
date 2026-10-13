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

daemon 只接受 `PURE_SIM`、`DEVICE_SIM`、`LIVE`。`OrcaDaemonBackend.map_control_run_mode` 把 `MOCK` 固定写成 `PURE_SIM`。不要在三个合法值里再猜一个。

## 2026-10-12 Orca MVC Phase 2

### 不要为了读端口去 import orca.daemon

`lifecycle.py` 会带上 psutil 以及更上游的运行时。控制面只需要 JSON 里的 `port`。在 `daemon_backend.py` 里自己解析 `daemon.json`，测试才能继续 `--confcutdir=tests/orca_mvc`。

### stop 必须两步

`confirm=true` 在尚未 armed 时不会 abort，只会暂停并把 abort 置为 armed。客户端取消要先 `confirm=false`，看到 `status=armed` 再 `confirm=true`。

### EventSource 不能加 Authorization

令牌放在 `GET /api/v1/events?token=`。其它路由不要读这个查询参数，避免访问日志里到处都是令牌。httpx 的 ASGITransport 会把 SSE 缓冲到连接结束，测 SSE 要用原始 ASGI，读到 hello 就断开。

### sim 不要标成 mock，也不要标成 live

进程内 stub 和消息总线是模拟线协议，`mode=sim`。纯内存日志才是 `mock`。rclpy 即使 import 成功，也没有机械臂，健康字段可以写 `message-bus+rclpy`，mode 仍是 sim。

## 2026-10-13 PURE_SIM 夹具

### `orca workflow load` 一次一个模板

`POST /workflows` 调用 `build_workflow(topology)`，返回值必须是单个 `WorkflowTemplate`，响应里也只有一个 `workflow_name`。两条协议就要两个 `module:build_workflow`。不要写一个工厂指望它登记两个名字。

### daemon 从启动时的当前目录导入

`python -m orca.daemon` 把当前目录放进 `sys.path`。`examples/` 不在 `src` 的安装包里。`pip install -e .` 之后如果在别的目录 `orca start`，`examples.mvc_daemon_sim` 会 404。文档里的命令都从仓库根复制。

### 纯模拟夹具要自己绑 SimDeviceFactory

挂载时外层是 `RemoteDeviceFactory`。只靠 `--sim` 和提交 `PURE_SIM`，收尾的 `reset_world` 仍可能打到 live 槽并被拒绝（日志里是 PURE_SIM 不能进设备桥）。夹具在 `build_topology` 里 `use_device_factory(SimDeviceFactory())`，两个槽都是进程内驱动，再加 `sim_override=PURE_SIM`。

### 板回到起点后，下一次提交会 409

线程 `start` 和 `end` 都是 `pad`。执行完成或 abort 后板还在 pad 上，再提交同一条 workflow 得到 `start_location_occupied`。清场用 `POST /labware/runtime/clear-all`，body `{"force": true}`，或 `orca labware clear-all --yes`。

### 包的 `__init__` 不要在导入时拉 orca

`tests/orca_mvc` 用 `--confcutdir` 躲开上游 conftest。测试若 `import examples.mvc_daemon_sim`，父包一导入就执行。工厂放在 `__getattr__` 里，离线用例只读 `specs.py`。
