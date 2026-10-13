# 规划文档（plan.md）

> 路径约定：`ref/plan.md`  
> 基于：`ref/requirement.md`、`doc/spec/ds.md`  
> 更新日期：2026-10-12

## 1. 方案概述

采用 **旁路 MVC 扩展**：新建 `src/orca_mvc/`（备选 `extensions/mvc/`），通过适配层调用 Orca `SystemRuntime` / daemon REST；Phase1 允许 **MockRuntimeBackend**，以便在未完整安装驱动栈时跑通控制面。SiLA2/ROS2/MCP/Web 均挂在控制面，不侵入 `reservation_manager`。

```mermaid
flowchart TB
  UI[View: Vite+TS Web]
  MCP[MCP Server]
  API[Controller: FastAPI Control Plane]
  Model[Model: Task/Cluster/Adapters]
  Backend[RuntimeBackend Interface]
  Real[Orca Runtime/Daemon]
  Mock[MockRuntimeBackend]
  UI --> API
  MCP --> API
  API --> Model
  Model --> Backend
  Backend --> Real
  Backend --> Mock
```

## 2. 阶段划分

### Phase 0 — 文档与契约（本交付）

- 调研专报、intent、requirement、plan、urs、ds、progress、索引。  
- **出口**：设计可指导编码；验收清单明确。  

### Phase 1 — MVC 扩展最小闭环（优先实现）

| 工作包 | 内容 | 负责人建议 |
|--------|------|------------|
| WP1 模型 | ExperimentTask、Workcell、Cluster、状态枚举、JSON 拓扑 | Engineer |
| WP2 控制面 API | FastAPI：tasks CRUD/提交、cluster 查询、adapters 状态 | Engineer |
| WP3 RuntimeBackend | Protocol + Mock；可选 DaemonClient | Engineer |
| WP4 适配器 stub | SiLA2/ROS2 mock | Engineer |
| WP5 MCP | tools 包装控制面 | Engineer |
| WP6 前端 | Vite+TS 独立端口，任务列表+cell 状态 | Engineer |
| WP7 测试与 README | pytest + 启动说明 | Engineer |
| WP8 审核 | 对照 URS/DS、安全与解耦审查 | Reviewer |

**Phase1 出口**：验收清单全部勾选。

### Phase 2 — 本机 daemon、令牌、无硬件联调（本交付）

不接物理实验设备。不改 `src/orca` 的预约、死锁、SystemMap。

| 工作包 | 内容 | 状态 |
|--------|------|------|
| WP2.1 Daemon HTTP | `OrcaDaemonBackend` 按 `DAEMON_ROUTE_CATALOG` 发请求。地址：`ORCA_DAEMON_URL`，否则 `~/.orca/daemon.json` 的 `port`。不猜 8000 | 已实现 |
| WP2.2 run_mode | 控制面 `MOCK` → daemon `PURE_SIM`。`DEVICE_SIM` / `LIVE` 原样 | 已实现 |
| WP2.3 默认执行面 | 未设置 `ORCA_MVC_RUNTIME` 时仍是 Mock。`daemon` 才用 HTTP 客户端。健康检查给出 `runtime_backend` 与 `daemon_reachable` | 已实现 |
| WP2.4 本机认证 | `ORCA_MVC_API_TOKEN` Bearer。默认本机开放并警告。`ORCA_MVC_AUTH=required` 或非回环绑定则必须有令牌。MCP 把同一令牌转给控制面。不是 OAuth | 已实现 |
| WP2.5 SiLA2 sim | 进程内 HTTP stub（`/sila/v1/features/...`），`mode=sim`。不是 gRPC，不连设备 | 已实现 |
| WP2.6 ROS2 sim | 记录回放 + 进程内总线，`mode=sim`。`ORCA_MVC_ROS2=rclpy` 失败则退回总线 | 已实现 |
| WP2.7 前端 | 执行面、daemon 可达、认证是否要求令牌；令牌来自 `VITE_ORCA_MVC_API_TOKEN` 或 localStorage | 已实现 |
| WP2.8 测试 | MockTransport 覆盖提交/查询/两段式停止。活 daemon 只保留可选 skip 的 `/health` | 已实现 |

**Phase2 出口**：pytest `tests/orca_mvc --confcutdir=tests/orca_mvc` 通过；README 写明 mock 与 `orca start` + `PURE_SIM` + `ORCA_MVC_RUNTIME=daemon` 的差别。

**留给后续、本阶段不做**：

- 真实 SiLA2 gRPC 设备与认证过的 Feature 实现  
- 依赖 ROS 图的机械臂节点（Humble/Jazzy 真机）  
- OAuth2 / 多用户  
- 前端 blocker / recovery 面板（SSE 在 Phase1 已有）  
- 在未挂载 workflow 的 daemon 上假装 `plate_readout` 能跑完  

### Phase 2 任务明细

1. 用 httpx 实现 submit / get / list / stop，状态字映射进控制面枚举。  
2. 取消走两段式 stop：`confirm=false` 再 `confirm=true`。  
3. 健康检查区分执行面名称和 daemon 是否可达。  
4. Bearer 中间层（FastAPI 依赖）+ MCP 客户端带头。SSE 只用查询参数带令牌。  
5. SiLA2 stub 与适配器；ROS2 jsonl 回放与总线；保留纯内存 mock 类供对照。  
6. 前端药丸与令牌框。  
7. 文档：本文件、`ref/progress.md`、`src/orca_mvc/README.md`、`doc/spec/ds.md`。  

### Phase 3 — 集群调度策略

- 任务到 workcell 的分配启发式/CP-SAT；  
- 跨 cell 转运与 Orca Translator 拓扑对齐；  
- 指标与仿真回放。  

## 3. 任务拆解（Phase1 明细）

1. 创建包结构与 pyproject 入口（若独立）或命名空间包。  
2. 实现模型与内存仓库（InMemoryTaskStore）。  
3. 实现 Control Plane 路由与 Pydantic schema。  
4. 实现 MockRuntimeBackend（异步 sleep 模拟执行）。  
5. 实现 adapters mock。  
6. 实现 MCP server（可用 `mcp` SDK 或最小 JSON-RPC 演示；需在 README 写明依赖）。  
7. 实现 frontend 最小页。  
8. 示例：`examples/mvc_cluster_two_cells.json`。  
9. pytest：test_tasks_parallel、test_cluster_load、test_adapters、test_mcp_tools。  
10. 更新 `ref/progress.md`。  

## 4. 多智能体协同

| 角色 | 职责 |
|------|------|
| 统筹/架构（本角色） | 需求、设计、验收标准、接口边界 |
| Engineer_Grok | 按 ds/plan 编码、单测、README |
| Reviewer_Grok | 对照 URS 审查解耦/安全/契约；缺陷回写 issues |

协作规则：Engineer 不改上游预约内核；Reviewer 以「可回滚、有测试、契约一致」为门禁。

## 5. 测试方案（Phase1）

- 单元：模型状态迁移、拓扑解析。  
- API：httpx/TestClient 提交双任务。  
- 适配器：mock 调用返回。  
- MCP：直接调 tool 函数或测试客户端。  
- 手工：按 README 启前后端截图/日志。  

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 上游驱动栈安装重 | MockRuntimeBackend 默认 |
| SSPL/安全 | 文档警示；默认 localhost |
| 范围膨胀 | Phase1 冻结真机与鉴权 |
| 双主状态 | ledger 仍以 Orca 为准；控制面只映射任务状态 |

## 7. 日程建议（弹性）

- D0：文档（完成）  
- D1–D2：WP1–WP3  
- D2–D3：WP4–WP6  
- D3：WP7–WP8  
