# 用户需求规格摘要（URS）

> 路径约定：`doc/spec/urs.md`  
> 依据：`ref/intent.md`、`ref/requirement.md`  
> 更新日期：2026-10-10  
> 说明：本 URS 为摘要级规格，供 DS 与测试追溯；详细叙事见 requirement 与调研专报。

## 1. 目的

规定 orca_2 在 Orca Framework 之上增加 MVC 扩展后，用户（实验室工程师、集成开发者、AI agent）应获得的能力与验收条件。

## 2. 用户与用例

| 用户 | 主要用例 |
|------|----------|
| 实验室操作/工程师 | 并行提交多个实验任务；查看任务与 workcell 状态；在 Web 上监控 |
| 集成开发者 | 配置双 cell 集群拓扑；接入 SiLA2/ROS2 适配器契约；编写测试 |
| AI agent | 通过 MCP tools 列表/提交/查询任务 |

## 3. 需求条目

### URS-01 多实验任务并行

系统应允许用户提交多个实验任务实例，并在仿真/mock 环境下并行运行与独立跟踪状态。

**验收**：连续提交 2 个任务，二者均可进入 running 并最终完成（或明确失败原因）；`GET` 列表可区分。

### URS-02 任务生命周期管理

系统应提供任务创建/查询/列表/取消（或等价终止）能力。

**验收**：API 与 MCP `get_status`/`list_tasks` 返回一致的状态枚举。

### URS-03 多 Workcell 集群拓扑

系统应支持描述至少两个 workcell 及其连接关系，并查询拓扑与各 cell 状态。

**验收**：加载示例 JSON；API 返回 2 个 cell；跨 cell 转运占位字段存在。

### URS-04 映射到 Orca 工作流层级

实验任务应能引用已注册的 protocol/workflow；设计上明确映射到 Workflow → Thread → Method → Action → Driver 链路（Phase1 可用 mock 代替真实提交）。

**验收**：DS 中有映射表；代码中 `ProtocolRef`/`workflow_name` 字段存在。

### URS-05 SiLA2 接口集成（Phase1 mock）

系统应提供 SiLA2 适配器接口与 mock 实现，可报告连接状态并执行一次模拟命令。

**验收**：健康检查 online；`call_command` 返回 mock 结果；无真机依赖。

### URS-06 ROS2 接口集成（Phase1 mock）

系统应提供 ROS2 适配器接口与 mock 实现，可列出话题/服务并模拟 publish/call。

**验收**：同 URS-05 量级。

### URS-07 MCP Server

系统应基于控制面 API 提供 MCP Server，至少暴露 `list_tasks`、`submit_task`、`get_status`。

**验收**：工具可调用且与 REST 结果一致；README 说明启动方式与安全边界。

### URS-08 分离式 Web 前端

系统应提供与后端分离端口的 Web 前端，展示任务列表与 workcell 状态，并可提交演示任务。

**验收**：浏览器打开前端 URL 可见数据；刷新后状态更新（轮询或 SSE）。

### URS-09 非侵入扩展

扩展实现不得破坏上游核心包的默认行为；优先独立包路径。

**验收**：Reviewer 确认无强制修改 `reservation_manager` 内核；上游示例仍可按官方文档运行（若环境具备）。

### URS-10 质量与文档

应有 pytest 关键路径覆盖与中文/英文混排文档（中文说明 + 英文标识符），含启动说明。

**验收**：CI 或本地 `pytest` 通过；`README` 可跟做。

## 4. 假设与约束

- A1：Phase1 可在无硬件、甚至无完整 cheshire-drivers 环境下用 MockRuntimeBackend 验收控制面。  
- A2：daemon 无认证；部署默认 localhost。  
- A3：工作流来自白名单/预注册，不接受匿名任意代码上传。  
- C1：许可 SSPL 可能限制某些 SaaS 形态。  
- C2：路径规划与死锁逻辑仍由上游负责。  

## 5. 追溯

| URS | requirement | DS 章节 | 测试建议 |
|-----|-------------|---------|----------|
| URS-01 | FR-T3 | Model/Controller 任务 | test_tasks_parallel |
| URS-02 | FR-T1/T2/T4 | API schemas | test_task_lifecycle |
| URS-03 | FR-C1/C2/C3 | Cluster 模型 | test_cluster_load |
| URS-04 | FR-T1 | 映射表 | 设计审查 |
| URS-05 | FR-A1 | Adapters | test_sila2_mock |
| URS-06 | FR-A2 | Adapters | test_ros2_mock |
| URS-07 | FR-M1/M2 | MCP | test_mcp_tools |
| URS-08 | FR-U1/U2/U3 | View | 手工 + 可选 e2e |
| URS-09 | NFR-1 | 包结构 | 代码审查 |
| URS-10 | FR-Q1/Q2 | README | pytest |
