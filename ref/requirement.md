# 需求文档（requirement.md）

> 路径约定：`ref/requirement.md`  
> 基于：`ref/intent.md`、上游 Orca 文档与源码调研专报  
> 更新日期：2026-10-10

## 1. 背景

实验室自动化中控需要：并行实验、设备预约与转运、故障恢复、可仿真验证。开源 Orca Framework 提供 Python 工作流（`@orca.action/method/thread/workflow`）、动态预约调度、SystemMap 路径打分、localhost daemon（REST+SSE）。官方将网络认证 REST/MCP/WebSocket 放在商业 Orca AI。Fork `orca_2` 已建立 AGENTS 文档体系，需要在开源内核之上补齐集群控制面与标准接口。

## 2. 环境

| 项 | 说明 |
|----|------|
| 上游 | https://github.com/Cheshire-Labs/orca |
| Fork | https://github.com/Hanson-83/orca_2 ；本地 `D:\Projects\orca_2` |
| 语言 | 文档中文；代码标识符英文；注释中文可接受 |
| 运行 | Python 3.10+（与上游一致）；前端 Node/Vite+TS |
| 约束 | 遵守仓库 `AGENTS.md`、`spec/*`；SSPL 许可需产品化前法务评估 |

## 3. 目标

1. 完成 Orca 调研专报（架构/模型/调度/路径/链路/VWorks 对照/缺口）。  
2. 设计并实现 **MVC 扩展**（建议 `src/orca_mvc/`），支撑：  
   - 多 ExperimentTask 并行提交与状态管理；  
   - 多 Workcell 集群拓扑与跨 cell 转运占位；  
   - SiLA2、ROS2 适配器（Phase1 mock）；  
   - 基于 REST API 的 MCP Server；  
   - 与后端分离的 Web 前端。  
3. Phase1 达到可演示、可测试的最小闭环。

## 4. 功能性需求（摘要）

### 4.1 实验任务控制面

- FR-T1：可创建/提交实验任务（引用已注册 protocol/workflow、run_mode、目标 workcell、参数）。  
- FR-T2：可列表/查询任务状态（至少：pending/running/completed/failed/cancelled）。  
- FR-T3：支持 ≥2 任务并行处于 running（仿真或 mock runtime 下）。  
- FR-T4：可取消未完成任务（契约级；若底层 execution 取消为 stub，须标明）。  

### 4.2 集群与 Workcell

- FR-C1：支持 JSON/Python 描述 Cluster = 多个 Workcell + 连接（桥/传递窗占位）。  
- FR-C2：至少提供 2-cell 示例拓扑。  
- FR-C3：跨 cell 转运在 Phase1 可为占位状态机（requested/in_transit/arrived），不要求真实臂。  

### 4.3 适配器

- FR-A1：SiLA2Adapter 接口：connect/disconnect/list_features/call_command（mock）。  
- FR-A2：Ros2Adapter 接口：connect/list_topics/publish/call_service（mock）。  
- FR-A3：控制面可查询适配器健康状态。  

### 4.4 MCP Server

- FR-M1：基于控制面 API 暴露 tools：`list_tasks`、`submit_task`、`get_status`（可扩展 `list_workcells`）。  
- FR-M2：本机可启动；文档声明非生产鉴权。  

### 4.5 前端 Web

- FR-U1：独立前端服务（与后端不同端口）。  
- FR-U2：展示任务列表与 workcell/集群状态。  
- FR-U3：可触发提交任务（对演示 workflow）。  

### 4.6 测试与文档

- FR-Q1：pytest 覆盖控制面关键路径（任务并行、拓扑加载、适配器 mock、MCP tool 至少冒烟）。  
- FR-Q2：README 启动说明；URS/DS/plan/progress 齐备。  

## 5. 非功能性需求

- NFR-1：扩展代码与上游 `src/orca` 解耦，避免修改预约内核除非必要且评审通过。  
- NFR-2：UTF-8 文档；接口 OpenAPI 或等价契约可生成/手写。  
- NFR-3：默认绑定本机回环；若监听 0.0.0.0 必须文档警告。  
- NFR-4：日志可追踪 task_id / workcell_id。  

## 6. 现状

- 上游具备 Runtime/Daemon/预约调度/路径打分/事件总线。  
- Fork 具备 AGENTS 模板，业务扩展文档与代码待填。  
- 官方 MCP 不在开源 daemon 默认范围。  

## 7. 参考

- 调研专报：`doc/专报_Orca开源中控框架调研.md`  
- https://cheshirelabs.io/docs/orca/intro  
- https://cheshirelabs.io/docs/orca/architecture/  
- 仓库 `AGENTS.md`  

## 8. 范围 / 边界

**范围内（Phase1）**：MVC 骨架、mock 适配器、MCP tools、分离前端、双 cell 示例、测试与文档。  

**范围外（Phase1）**：真机 SiLA2/ROS2、生产鉴权、全局优化调度、改写 SystemMap/Deadlock 内核、任意用户上传 Python 工作流执行。  

## 9. 验收标准（总览）

见 `doc/spec/urs.md` 与下文清单；全部 Phase1 验收项勾选且文档索引可读即本轮需求达标。

### Phase1 验收清单

- [ ] 调研专报已入库且含证据 URL 与 mermaid  
- [ ] intent/requirement/plan/urs/ds/progress/README 齐全  
- [ ] `orca_mvc`（或约定包名）可安装/可导入  
- [ ] 双任务并行提交与状态 API 演示通过  
- [ ] 双 workcell 拓扑加载与查询通过  
- [ ] SiLA2/ROS2 mock 健康检查通过  
- [ ] MCP tools 冒烟通过  
- [ ] 前端独立端口可打开并显示任务/cell  
- [ ] pytest 关键路径绿  
- [ ] README 启动步骤可跟做  
