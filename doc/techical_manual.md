# 技术说明：Orca MVC 控制面（Phase 1）

## 1. 定位

在不改上游 `src/orca` 预约、死锁和 SystemMap 的前提下，加一个本机控制面：

- 模型：ExperimentTask、Workcell、Cluster、协议到 WorkflowTemplate 的名字映射
- 控制器：FastAPI，`http://127.0.0.1:8100/api/v1`
- 视图：`web/`，Vite + TypeScript，`http://127.0.0.1:5173`，开发服务器把 `/api` 代理到 8100
- 执行面：`MockRuntimeBackend` 模拟 `queued → running → completed`
- 设备侧：SiLA2 / ROS2 的 mock，只记内存日志
- 智能体侧：MCP stdio 工具 `list_tasks`、`submit_task`、`get_status`、`list_workcells`

启动、环境变量和安全警告见 `src/orca_mvc/README.md`。

## 2. 和 Orca 的边界

ExperimentTask 提交后，响应里的 `mapping` 会写上计划中的 daemon 调用：

- `POST /executions`
- body 键：`workflow_name`、`variables`、`run_mode`
- `phase` 固定为 `not_called`

Phase 1 不会请求 daemon。`ORCA_MVC_RUNTIME=daemon` 时提交返回 HTTP 501。

已核对、供 Phase 2 使用的路由（见 `src/orca_mvc/runtime/daemon_backend.py`）：

| 用途 | 方法与路径 |
|------|------------|
| 提交 workflow | `POST /executions` |
| 列出执行 | `GET /operations/list-executions` |
| 查询一条 | `POST /operations/get-execution` |
| 查询详情 | `POST /operations/get-execution-detail` |
| 停止 | `POST /operations/stop-execution`（两段式 confirm） |
| 移除 | `POST /operations/remove-execution` |

端口不写死。读 `~/.orca/daemon.json` 的 `port`，或由调用方设置 `ORCA_DAEMON_URL`。daemon 只监听 `127.0.0.1`。

`MOCK` 要在 Phase 2 映射成 `PURE_SIM`、`DEVICE_SIM` 或 `LIVE` 之一后再提交。

## 3. 集群与转运

启动时加载 `src/orca_mvc/scenarios/cluster_two_cells.json`：`cell_a`、`cell_b`，链路 `bridge_ab`（`translator`，不支持 deadlock parking）。

`POST /api/v1/cluster/transfers` 只接受拓扑里已经声明的有向链路。状态机 `requested → in_transit → arrived` 是占位，不调用 Orca Translator。`fault` / `offline` 保持拓扑原值；`idle` / `busy` 按是否有 running 任务推导。

## 4. 迁移与回滚

- 新环境：Python 3.10+，安装仓库已有的 FastAPI 栈；MCP 另装 `mcp>=1.9,<3`。前端在 `web/` 执行 `npm install && npm run dev`。
- 不需要 cheshire-drivers 就能跑控制面和 `tests/orca_mvc`。
- 回滚：还原本分支引入的 `src/orca_mvc`、`web`、`tests/orca_mvc` 以及 `pyproject.toml` / `.gitignore` 的附加项。`src/orca` 无行为变更。

## 5. 已知缺口

无认证。状态在内存中，进程退出即丢失。没有真实 SiLA2 客户端，没有 rclpy，没有任务到 workcell 的优化分配。
