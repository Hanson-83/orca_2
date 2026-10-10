# Orca MVC 控制面（Phase 1）

旁路包，不修改上游预约、死锁和 SystemMap。控制面管理实验任务和 workcell 集群；执行面在这一阶段用 `MockRuntimeBackend` 模拟时间线。真实 `SystemRuntime` / daemon 接线留到 Phase 2，路由以 `runtime/daemon_backend.py` 里对照源码整理的表为准。

**没有认证。** 默认只监听 `127.0.0.1`。不要把控制面、MCP 或前端开发服务器暴露到局域网或公网。

## 依赖

控制面使用仓库里已有的 `fastapi`、`uvicorn`、`pydantic`、`httpx`。MCP 是可选额外依赖：

```bash
python -m pip install 'mcp>=1.9,<3'
```

或在安装本仓库时加上 extra：`pip install -e '.[mvc]'`。整包安装会拉取上游驱动栈；只跑控制面时把 `src` 放进 `PYTHONPATH` 即可。

MCP SDK 2.x 里，原来的 `FastMCP` 已改名为 `MCPServer`（`mcp.server.mcpserver`）。本包按 2.x 编写。

## 启动

三个进程，都在仓库根目录操作。下面假设当前目录是仓库根。

```bash
# 1. 控制面 API，127.0.0.1:8100
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

浏览器打开 `http://127.0.0.1:5173`。页面是中文：任务列表、提交表单、workcell 状态、适配器模拟调用。数据走 SSE，同时每 2 秒轮询一次。

健康检查：`GET http://127.0.0.1:8100/api/v1/health`

交互文档：`http://127.0.0.1:8100/docs`

## 这一阶段实际做了什么

| 能力 | 行为 |
|------|------|
| 多任务 | `POST /api/v1/tasks` 创建 pending，`POST /api/v1/tasks/{id}/submit` 提交。内存存储，可同时处于 running |
| 集群 | 启动时加载 `scenarios/cluster_two_cells.json`（cell_a、cell_b）。`POST /api/v1/cluster/load` 可换拓扑 |
| 跨 cell | `POST /api/v1/cluster/transfers` 只在已声明的链路上创建占位，状态 `requested → in_transit → arrived` |
| 协议映射 | `plate_readout`、`seal_and_shake` 映射到同名 WorkflowTemplate。响应里的 `mapping.orca_submit.phase` 固定是 `not_called` |
| SiLA2 / ROS2 | mock。启动时 connect。调用记在内存日志里，`GET /api/v1/adapters` 能看到 |
| MCP | `list_tasks`、`submit_task`、`get_status`，外加 `list_workcells`。stdio 不监听端口 |
| 执行面 | `MockRuntimeBackend` 按排队、运行、完成推进。`ORCA_MVC_RUNTIME=daemon` 会选用骨架，提交返回 501，不会发 HTTP |

预注册协议之外的 `protocol_ref` 会被拒绝。daemon 的 `run_mode` 只有 `PURE_SIM`、`DEVICE_SIM`、`LIVE`。控制面的 `MOCK` 不能原样提交给 `POST /executions`，Phase 2 要做显式映射。

## Daemon 接线时要用的真实路由

这些路径是从 `src/orca/daemon/routes.py` 和 `operations_router.py` 抄下来的，不是设计稿里的猜测：

- `POST /executions`：`workflow_name`、`variables`、`run_mode`、`acknowledge_warnings`、`profile_path`
- `GET /operations/list-executions`
- `POST /operations/get-execution`，body `{execution_id}`
- `POST /operations/stop-execution`，body `{execution_id, confirm}`。第一次只暂停并 armed，`confirm=true` 的下一次才 abort
- 端口写在 `~/.orca/daemon.json` 的 `port` 字段（目录可用 `ORCA_DAEMON_HOME` 改）。进程只绑 `127.0.0.1`。没有固定的 8000 端口

Phase 2 再用 `ORCA_DAEMON_URL` 指向这个地址。当前骨架即使设置了该变量也不会发请求。

## 环境变量

| 变量 | 默认 | 作用 |
|------|------|------|
| `ORCA_MVC_HOST` | `127.0.0.1` | 控制面监听地址。改成非回环地址时会打警告 |
| `ORCA_MVC_PORT` | `8100` | 控制面端口 |
| `ORCA_MVC_RUNTIME` | `mock` | `mock` 或 `daemon`（后者只拒绝调用） |
| `ORCA_MVC_API_URL` | `http://127.0.0.1:8100` | MCP 要连的控制面 |
| `ORCA_MVC_MCP_TRANSPORT` | `stdio` | `stdio` 或 `streamable-http` |
| `ORCA_MVC_MCP_HOST` / `ORCA_MVC_MCP_PORT` | `127.0.0.1` / `8101` | 仅 HTTP 传输时使用 |
| `ORCA_MVC_CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | 逗号分隔 |
| `VITE_API_BASE` | 空 | 前端直连 API 时填写，例如 `http://127.0.0.1:8100`。开发服务器走代理时留空 |

模拟节奏：`ORCA_MVC_STEP_DELAY`（进入 running 前）、`ORCA_MVC_RUNNING_HOLD`（running 保持）、`ORCA_MVC_TRANSFER_STEP`（转运每一步）。

## 测试

```bash
python -m pytest tests/orca_mvc --confcutdir=tests/orca_mvc
```

`--confcutdir` 用来跳过 `tests/conftest.py`。那个文件会导入上游 `orca`，而控制面测试不需要驱动栈。用例自己把 `src` 加进 `sys.path`。

## 目录

```text
src/orca_mvc/
  models/        ExperimentTask、Workcell、Cluster、协议映射
  store/         内存任务表
  services/      控制面
  api/           FastAPI，前缀 /api/v1
  runtime/       RuntimeBackend、Mock、daemon 骨架
  adapters/      sila2_mock.py、ros2_mock.py
  mcp_server/    MCP 工具
  scenarios/     cluster_two_cells.json
web/             Vite + TypeScript 前端
tests/orca_mvc/  pytest
```
