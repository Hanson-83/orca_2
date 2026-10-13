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

- 新环境：Python 3.10+，安装仓库已有的 FastAPI 栈；MCP 另装 `mcp>=2,<3`（extra `mvc`）。前端在 `web/` 执行 `npm install && npm run dev`。
- 跑 `tests/orca_mvc` 的 CI 必须安装 `[mvc]`。缺 `mcp` 时对应用例失败，不会跳过。
- 不需要 cheshire-drivers 就能跑控制面和 `tests/orca_mvc`。
- 回滚：还原本分支引入的 `src/orca_mvc`、`web`、`tests/orca_mvc` 以及 `pyproject.toml` / `.gitignore` 的附加项。`src/orca` 无行为变更。

## 5. 已知缺口

状态在内存中，进程退出即丢失。没有认证过的 SiLA2 gRPC 客户端，没有连着机械臂的 ROS 节点，没有任务到 workcell 的优化分配。默认仍可不设令牌（仅本机）。blocker / recovery 面板未做。

## 6. Phase 2（2026-10-12）

`OrcaDaemonBackend` 会发 HTTP。路由仍以第 2 节的表为准，并增加探测用的 `GET /health`（响应里 `daemon` 必须是 `ok`）。

- 地址：`ORCA_DAEMON_URL`，否则读 `daemon.json` 的 `port`。不导入 `orca.daemon`，避免控制面测试拉起驱动栈。
- `MOCK` 在客户端里写成 `PURE_SIM` 再放进 `POST /executions`。
- 取消固定两步：`confirm=false`，返回 `armed` 后再 `confirm=true`。这是 `SystemRuntime.stop_execution` 的契约：单次 `confirm=true` 在尚未 armed 时只暂停。
- 控制面默认仍是 Mock。`ORCA_MVC_RUNTIME=daemon` 才换客户端。健康检查同时给出后端名字和 daemon 是否可达。
- 认证是共享密钥 Bearer，见 `src/orca_mvc/auth.py`。SSE 用查询参数，因为 EventSource 不能设请求头。
- SiLA2 sim 的 stub 在 `adapters/sila2_stub.py`。ROS2 sim 回放 `scenarios/ros2_trace.jsonl`。`mode` 标 `sim`，不要标成 live。
- 回滚：git 还原本阶段提交。修改前的包副本在执行环境的 `/tmp/orca_mvc_phase2_backup/before.tar`（不进仓库）。

第 2 节里「Phase 1 不会请求 daemon、`ORCA_MVC_RUNTIME=daemon` 返回 501」只描述 Phase 1。Phase 2 起，没有地址时是 503 `DAEMON_UNAVAILABLE`，有地址时会真正 POST。

## 7. Phase 2A 本机 PURE_SIM 配方（2026-10-13）

控制面协议名 `plate_readout`、`seal_and_shake` 要对上 daemon 里的 WorkflowTemplate。`examples/mvc_daemon_sim/` 提供：

- `examples.mvc_daemon_sim:build_topology`
- `examples.mvc_daemon_sim.plate_readout:build_workflow`
- `examples.mvc_daemon_sim.seal_and_shake:build_workflow`

`orca workflow load` 对应 `POST /workflows`，一次只接受一个返回 `WorkflowTemplate` 的工厂，所以是两次 load，不是一个工厂登记两个名字。

拓扑是板位 `pad`、读板机、封膜机、振荡器、机械臂 `robot`。示教点经 `stores.teachpoints` / `stores.access_configs` 写入 daemon 传入的 store。构造设备时改绑 `SimDeviceFactory`（覆盖 daemon 挂载时的 `RemoteDeviceFactory`），两个驱动槽都是进程内 Sim*。`sim_override=PURE_SIM` 再挡一层。`--sim` 只影响 daemon 的诊断标记，提交时的 `run_mode` 仍由控制面把 `MOCK` 写成 `PURE_SIM`。

线程从 `pad` 出发再回到 `pad`。跑完或 abort 之后板还在 `pad` 上，下一次提交会 409 `start_location_occupied`。冒烟在停止后 `POST /labware/runtime/clear-all`（`force=true`）。手工等价命令是 `orca labware clear-all --yes`。

动作在设备调用后睡眠约 8 秒，便于两段式 stop。耗材用 `SimPlateTemplate`，不查 PLR 目录。

冒烟脚本 `python -m examples.mvc_daemon_sim.smoke` 打控制面 `GET /api/v1/health`（要 `daemon_reachable` 且 `runtime=orca-daemon`），创建并提交 `plate_readout`，再对 daemon `GET /operations/list-executions` 和两次 `POST /operations/stop-execution`。包的 `__init__` 用懒加载，`import examples.mvc_daemon_sim` 不导入 orca，离线测试才能过。

`orca start` 的工作目录必须是仓库根。可编辑安装不会把 `examples/` 放进 site-packages。

回滚：git 还原本阶段提交。修改前的文档副本在 `/tmp/orca_mvc_phaseA_backup/`（不进仓库）。`src/orca` 无改动。
