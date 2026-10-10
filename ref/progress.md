# 进度状态（progress.md）

> 路径约定：`ref/progress.md`  
> 更新日期：2026-10-10

## 1. 总体状态

| 里程碑 | 状态 |
|--------|------|
| Phase0 调研与文档 | **已完成**（文档已落入仓库） |
| Phase1 MVC 编码 | **已完成**（本分支 `cursor/orca-mvc-phase1-93bf`） |
| Phase2 真联集成 | 未开始 |
| Phase3 集群优化调度 | 未开始 |

交付索引（不单独放仓库根目录）：

| 文档 | 路径 |
|------|------|
| 调研专报 | `doc/专报_Orca开源中控框架调研.md` |
| 意图 / 需求 / 规划 | `ref/intent.md`、`ref/requirement.md`、`ref/plan.md` |
| URS / DS | `doc/spec/urs.md`、`doc/spec/ds.md` |
| 控制面说明 | `src/orca_mvc/README.md` |
| 技术说明 | `doc/techical_manual.md` |

## 2. 任务状态

| ID | 任务 | 状态 | 备注 |
|----|------|------|------|
| T0 | 调研专报 | 完成 | `doc/专报_Orca开源中控框架调研.md` |
| T1 | intent/requirement/plan | 完成 | `ref/*` |
| T2 | urs/ds | 完成 | `doc/spec/*` |
| T3 | 交付索引 | 完成 | 写在本文件，不另放根目录 README |
| T4 | orca_mvc 包骨架 | 完成 | `src/orca_mvc/` |
| T5 | 控制面 API + MockRuntime | 完成 | `127.0.0.1:8100`，`/api/v1` |
| T6 | SiLA2/ROS2 mock | 完成 | 健康检查 + 模拟调用 |
| T7 | MCP Server | 完成 | 官方 `mcp` 2.x `MCPServer`，stdio |
| T8 | 前端 Web | 完成 | `web/`，Vite + TypeScript，`5173` |
| T9 | pytest + README | 完成 | `tests/orca_mvc` 20 通过；见 `src/orca_mvc/README.md`。CI 须安装 `[mvc]` |
| T10 | Reviewer 审核 | 进行中 | 已按意见补 SSE / lifespan / daemon 501、未知 SiLA Feature 拒绝，并取消 PR 草稿 |

## 3. 问题汇总

| ID | 描述 | 状态 |
|----|------|------|
| I1 | 上游 daemon 精确 REST 路径需对照源码 | **已核对并写入** `runtime/daemon_backend.py`。Phase 1 不调用。端口来自 `~/.orca/daemon.json`，没有固定 8000 |
| I2 | SSPL 对产品化形态的约束需法务确认 | 开放 |

## 4. 风险汇总

| ID | 风险 | 等级 | 应对 |
|----|------|------|------|
| R1 | 驱动栈安装失败阻断验收 | 中 | 已用 MockRuntimeBackend。测试用 `--confcutdir=tests/orca_mvc`，不导入上游 `tests/conftest.py` |
| R2 | 无鉴权误暴露 | 高 | 默认 `127.0.0.1`，README 写明警告 |
| R3 | 范围膨胀到真机 | 中 | daemon 后端提交即 501，不发 HTTP |

## 5. 后续行动

1. Reviewer 按 URS 验收清单审核本分支。  
2. Phase 2：按 `DAEMON_ROUTE_CATALOG` 实现 `OrcaDaemonBackend`，并把控制面 `MOCK` 显式映射到 daemon 的 `PURE_SIM` / `DEVICE_SIM` / `LIVE`。  
3. 认证、真实 SiLA2、rclpy 仍不在本阶段。

## 6. 剩余工作

Phase2 / Phase3 见 `ref/plan.md`。Phase1 编码、pytest 与前端构建已完成。

## 7. Phase1 验收

- [x] `src/orca_mvc/` 可导入，控制面可启动  
- [x] ≥2 个 ExperimentTask 并行提交与状态查询  
- [x] ≥2 workcell 集群 JSON 加载与查询；跨 cell 转运占位可用  
- [x] SiLA2 / ROS2 mock 健康检查与模拟调用  
- [x] MCP tools：`list_tasks`、`submit_task`、`get_status`  
- [x] 前端独立端口展示任务列表与 workcell 状态  
- [x] pytest 关键路径通过（20）  
- [x] README 启动说明可跟做  
- [x] 未改上游 `src/orca` 预约 / 死锁 / SystemMap 内核
