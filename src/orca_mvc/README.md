# Orca MVC 控制面（Phase 2）

旁路包，不修改上游预约、死锁和 SystemMap。控制面管理实验任务和 workcell 集群。

默认执行面是 `MockRuntimeBackend`，不连接 daemon。设置 `ORCA_MVC_RUNTIME=daemon` 后，`OrcaDaemonBackend` 按源码核对过的路由访问本机 Orca daemon。SiLA2 / ROS2 这一阶段是 **sim**：有可测的协议形状，没有机器人。

**认证默认关闭。** 未设置 `ORCA_MVC_API_TOKEN` 时，控制面在回环地址上开放，并在启动日志里警告。不要把控制面、MCP 或前端开发服务器暴露到局域网或公网。

## 依赖

控制面使用仓库里已有的 `fastapi`、`uvicorn`、`pydantic`、`httpx`。MCP 是可选额外依赖：

```bash
python -m pip install 'mcp>=2,<3'
```

或在安装本仓库时加上 extra：`pip install -e '.[mvc]'`。`[mvc]` 会装上 `mcp>=2,<3`。1.x 没有 `MCPServer`，不能用。整包安装会拉取上游驱动栈；只跑控制面时把 `src` 放进 `PYTHONPATH` 即可。

MCP SDK 2.x 里，原来的 `FastMCP` 已改名为 `MCPServer`（`mcp.server.mcpserver`）。本包按 2.x 编写。

## 用模拟执行面启动（不需要 orca daemon）

三个进程，都在仓库根目录操作。

```bash
# 1. 控制面 API，127.0.0.1:8100，执行面 mock
PYTHONPATH=src python -m orca_mvc.api

# 2. 另开终端。MCP 走 stdio，由客户端拉起；它会请求上面的 API
PYTHONPATH=src ORCA_MVC_API_URL=http://127.0.0.1:8100 python -m orca_mvc.mcp_server

# 3. 前端，127.0.0.1:5173，开发服务器把 /api 代理到 8100
cd web && npm install && npm run dev
```

等价的 uvicorn 命令：

```bash
PYTHONPATH=src uvicorn orca_mvc.api.app:app --host 127.0.0.1 --port 8100
```

浏览器打开 `http://127.0.0.1:5173`。页面显示执行面名称、daemon 是否可达、认证是否要求令牌。数据走 SSE，同时每 2 秒轮询一次。

健康检查：`GET http://127.0.0.1:8100/api/v1/health`

交互文档：`http://127.0.0.1:8100/docs`

## 接到本机 Orca daemon（PURE_SIM，仍然不要真机）

daemon 只绑 `127.0.0.1`。端口写在 `~/.orca/daemon.json` 的 `port`（目录可用 `ORCA_DAEMON_HOME` 改），**没有固定的 8000**。也可以用 `ORCA_DAEMON_URL` 覆盖，例如 `http://127.0.0.1:51293`。`ORCA_DAEMON_URL` 优先于 pid 文件。

控制面任务的 `run_mode=MOCK` 会显式映射成 daemon 的 `PURE_SIM` 再 `POST /executions`。`DEVICE_SIM` 和 `LIVE` 原样转发。`LIVE` 需要已经装好的设备和人工确认，这一阶段不要用它做演示。

```bash
# 终端 A：需要已安装的 orca CLI 与驱动栈。本仓库的控制面测试不启动这个进程。
orca start
orca topology mount '<module:build_topology>' --sim
orca workflow load '<module:build_workflow>'

# 终端 B：控制面改走 daemon。地址从 daemon.json 读。
ORCA_MVC_RUNTIME=daemon PYTHONPATH=src python -m orca_mvc.api
```

`POST /executions` 的 `workflow_name` 来自协议映射。预注册的名字是 `plate_readout` 和 `seal_and_shake`。daemon 里没有同名 WorkflowTemplate 时，提交会失败（控制面 502，任务 `failed`），这不是网络没接上。

没有 daemon 进程时不要设 `ORCA_MVC_RUNTIME=daemon`。设了但没有地址，提交返回 503 `DAEMON_UNAVAILABLE`，不会猜端口。健康检查里的 `daemon_reachable` 表示 `GET /health` 是否返回 `{"daemon":"ok"}`。

### 仍然需要活着的 daemon 才能演示的部分

单元测试用 `httpx.MockTransport`，不启动 daemon。下面这些只有本机 `orca start` 并且拓扑和 workflow 已经挂上之后才能看到：

- 控制面提交后，daemon 里出现一条真实 execution id
- `GET /operations/list-executions` 能列出这条执行
- 取消任务时两段式 `POST /operations/stop-execution`（先 `confirm=false` armed，再 `confirm=true` abort）
- 健康检查 `daemon_reachable: true`

可选集成测试 `tests/orca_mvc/test_daemon_live.py` 只打 `GET /health`。daemon 没起来就 skip。

## 这一阶段实际做了什么

| 能力 | 行为 |
|------|------|
| 多任务 | `POST /api/v1/tasks` 创建 pending，`POST /api/v1/tasks/{id}/submit` 提交。内存存储，可同时处于 running |
| 集群 | 启动时加载 `scenarios/cluster_two_cells.json`。`POST /api/v1/cluster/load` 可换拓扑 |
| 跨 cell | `POST /api/v1/cluster/transfers` 只在已声明的链路上创建占位 |
| 协议映射 | `plate_readout`、`seal_and_shake` 映射到同名 WorkflowTemplate |
| 执行面 mock | 默认。`mapping.orca_submit.phase` 是 `not_called`，不发 HTTP |
| 执行面 daemon | `ORCA_MVC_RUNTIME=daemon`。`POST /executions`，轮询 `POST /operations/get-execution`，取消走两段式 stop |
| SiLA2 | `mode=sim`。进程内 HTTP stub，路径 `/sila/v1/features/...`。不是 SiLA2 gRPC，也不连设备 |
| ROS2 | `mode=sim`。回放 `scenarios/ros2_trace.jsonl`，再走进程内话题/服务总线。`ORCA_MVC_ROS2=rclpy` 时若 rclpy 可用就旁路发一条 `std_msgs/String`，失败则退回总线，`mode` 仍是 sim |
| MCP | `list_tasks`、`submit_task`、`get_status`、`list_workcells`。调用控制面时带上 `ORCA_MVC_API_TOKEN` |
| 认证 | 见下一节。不是 OAuth |

手工把 SiLA2 stub 绑到端口：

```bash
PYTHONPATH=src python -m orca_mvc.adapters.sila2_stub
# 默认 127.0.0.1:8110
ORCA_MVC_SILA2_URL=http://127.0.0.1:8110 PYTHONPATH=src python -m orca_mvc.api
```

不设 `ORCA_MVC_SILA2_URL` 时，控制面用同一张路由表的进程内 ASGI，CI 不需要额外进程。

## 认证

只做本机 Bearer，没有 OAuth、没有用户目录。

| 条件 | 行为 |
|------|------|
| `ORCA_MVC_AUTH=optional`（默认），未设置令牌，`ORCA_MVC_HOST` 是回环地址 | 开放。启动时警告 |
| 设置了 `ORCA_MVC_API_TOKEN` | 除健康检查和文档页外，要求 `Authorization: Bearer <token>` |
| `ORCA_MVC_AUTH=required` | 必须校验令牌。令牌没配置时受保护接口返回 401，不会假装已保护 |
| `ORCA_MVC_HOST` 不是回环地址 | 视为必须认证。`python -m orca_mvc.api` 在没有令牌时直接退出 |

`GET /api/v1/events` 额外接受 `?token=`，因为浏览器 `EventSource` 不能加 Authorization。其它路径不读查询参数。

前端：构建时的 `VITE_ORCA_MVC_API_TOKEN` 优先；否则用浏览器 `localStorage` 键 `orca_mvc_api_token`。页面在 `auth_required` 时给出输入框。MCP 从环境变量 `ORCA_MVC_API_TOKEN` 读取，转发给控制面。streamable-http 绑到非回环地址时，没有令牌就拒绝启动。MCP 监听本身没有第二套 OAuth。

健康检查字段：

| 字段 | 含义 |
|------|------|
| `runtime` / `runtime_backend` | `mock` 或 `orca-daemon` |
| `daemon_reachable` | 本机 daemon 的 `GET /health` 是否为 `daemon=ok` |
| `daemon_url` | 解析到的地址；没有则为 null |
| `auth` | `none` 或 `bearer` |
| `auth_required` | 受保护接口是否要令牌 |
| `auth_configured` | 要求令牌时，令牌是否已经配置 |

## Daemon 路由

这些路径来自 `src/orca/daemon/routes.py` 和 `operations_router.py`，由 `tests/orca_mvc/test_daemon_contract.py` 回读源码锁住：

- `POST /executions`：`workflow_name`、`variables`、`run_mode`、`acknowledge_warnings`、`profile_path`。响应里的执行 id 是 `id`
- `GET /operations/list-executions`
- `POST /operations/get-execution`，body `{execution_id}`，响应 `{"execution": {..., "status": ...}}`
- `POST /operations/stop-execution`，body `{execution_id, confirm}`。`confirm=false` 只暂停并 armed；`confirm=true` 且已经 armed 才 abort
- `GET /health`：进程活着时 `daemon` 为 `ok`

daemon 的 `accepting` / `draining` / `stopping` / `running` 映射成控制面 `running`。`aborted` 映射成 `cancelled`。`completed` 和 `failed` 同名。

`variables` 只接受字符串、整数、浮点、布尔。嵌套对象会在出网前被拒绝（422）。

## 环境变量

| 变量 | 默认 | 作用 |
|------|------|------|
| `ORCA_MVC_HOST` | `127.0.0.1` | 控制面监听地址。非回环必须带令牌 |
| `ORCA_MVC_PORT` | `8100` | 控制面端口 |
| `ORCA_MVC_RUNTIME` | `mock` | `mock` 或 `daemon` |
| `ORCA_DAEMON_URL` | 空 | 例如 `http://127.0.0.1:51293`。优先于 pid 文件 |
| `ORCA_DAEMON_HOME` | `~/.orca` | 其下 `daemon.json` 提供 port |
| `ORCA_MVC_API_TOKEN` | 空 | Bearer 令牌。空则本机开放（见上表） |
| `ORCA_MVC_AUTH` | `optional` | `optional` 或 `required` |
| `ORCA_MVC_API_URL` | `http://127.0.0.1:8100` | MCP 要连的控制面 |
| `ORCA_MVC_MCP_TRANSPORT` | `stdio` | `stdio` 或 `streamable-http` |
| `ORCA_MVC_MCP_HOST` / `ORCA_MVC_MCP_PORT` | `127.0.0.1` / `8101` | 仅 HTTP 传输时使用 |
| `ORCA_MVC_CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | 逗号分隔 |
| `ORCA_MVC_SILA2_URL` | 空 | 指向 `sila2_stub`。空则进程内 ASGI |
| `ORCA_MVC_SILA2_HOST` / `ORCA_MVC_SILA2_PORT` | `127.0.0.1` / `8110` | 只在手工启动 stub 时使用 |
| `ORCA_MVC_ROS2` | `bus` | `bus`，或 `rclpy`（失败则退回总线） |
| `VITE_API_BASE` | 空 | 前端直连 API 时填写。开发服务器走代理时留空 |
| `VITE_ORCA_MVC_API_TOKEN` | 空 | 前端构建期令牌，优先于 localStorage |

模拟节奏：`ORCA_MVC_STEP_DELAY`、`ORCA_MVC_RUNNING_HOLD`、`ORCA_MVC_TRANSFER_STEP`、`ORCA_MVC_POLL_INTERVAL`。

## 测试

```bash
python -m pip install 'mcp>=2,<3'   # 或 pip install -e '.[mvc]'
python -m pytest tests/orca_mvc --confcutdir=tests/orca_mvc
```

`--confcutdir` 用来跳过 `tests/conftest.py`。那个文件会导入上游 `orca`，而控制面测试不需要驱动栈。用例自己把 `src` 加进 `sys.path`。

daemon 客户端测试使用 `httpx.MockTransport`，不要求 daemon 进程。`test_daemon_live.py` 在 daemon 未运行时 skip。CI 必须安装 `[mvc]`。MCP 用例直接导入 `mcp.server.mcpserver.MCPServer`，缺包时失败，不会 `importorskip` 跳过。

## 目录

```text
src/orca_mvc/
  models/        ExperimentTask、Workcell、Cluster、协议映射
  store/         内存任务表
  services/      控制面
  api/           FastAPI，前缀 /api/v1
  auth.py        本机 Bearer
  runtime/       MockRuntimeBackend、OrcaDaemonBackend
  adapters/      sila2 mock/sim/stub，ros2 mock/sim/bus
  mcp_server/    MCP 工具
  scenarios/     cluster_two_cells.json、ros2_trace.jsonl
web/             Vite + TypeScript 前端
tests/orca_mvc/  pytest
```
