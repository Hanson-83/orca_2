# 进度状态（progress.md）

> 路径约定：`ref/progress.md`  
> 更新日期：2026-10-12

## 1. 总体状态

| 里程碑 | 状态 |
|--------|------|
| Phase0 调研与文档 | **已完成**（文档已落入仓库） |
| Phase1 MVC 编码 | **已完成**（`cursor/orca-mvc-phase1-93bf`） |
| Phase2 本机 daemon / 令牌 / sim 适配 | **已完成**（本分支 `cursor/orca-mvc-phase2-daemon-2164`）。无物理设备 |
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
| T9 | pytest + README | 完成 | Phase1 基线。Phase2 起见 T14 |
| T10 | Reviewer 审核 | 完成 | Phase1 评审意见已合入 |
| T11 | OrcaDaemonBackend HTTP | 完成 | MockTransport 单测。`MOCK`→`PURE_SIM`。地址来自 `ORCA_DAEMON_URL` 或 `daemon.json` |
| T12 | 本机 Bearer | 完成 | 令牌可选；`required` 或非回环则强制。MCP 转发同一令牌 |
| T13 | SiLA2/ROS2 sim | 完成 | HTTP stub + 记录回放总线。`mode=sim`。无机器人 |
| T14 | pytest + 文档 | 完成 | `tests/orca_mvc` 40 passed、1 skipped（活 daemon）。`--confcutdir=tests/orca_mvc` |

## 3. 问题汇总

| ID | 描述 | 状态 |
|----|------|------|
| I1 | 上游 daemon 精确 REST 路径需对照源码 | **已核对并调用**。端口来自 `~/.orca/daemon.json` 或 `ORCA_DAEMON_URL`，没有固定 8000 |
| I3 | 预注册协议名在未挂载的 daemon 上不存在 | 开放。提交会 502。演示前要 `orca workflow load` 出同名模板 |
| I2 | SSPL 对产品化形态的约束需法务确认 | 开放 |

## 4. 风险汇总

| ID | 风险 | 等级 | 应对 |
|----|------|------|------|
| R1 | 驱动栈安装失败阻断验收 | 中 | 已用 MockRuntimeBackend。测试用 `--confcutdir=tests/orca_mvc`，不导入上游 `tests/conftest.py` |
| R2 | 无鉴权误暴露 | 中 | 默认仍开放，但只建议回环。非回环或 `ORCA_MVC_AUTH=required` 要 Bearer |
| R3 | 范围膨胀到真机 | 低 | Phase2 只做 HTTP 客户端和 sim 适配。`LIVE` 可转发，文档要求演示用 `PURE_SIM` |

## 5. 后续行动

1. 有驱动栈的环境里用 `orca start` + `topology mount --sim` + 同名 workflow 看一条真实 execution。单元测试替代不了这一步。  
2. blocker / recovery 面板、OAuth、SiLA2 gRPC、ROS 真节点仍未做。  
3. Phase 3 调度见 `ref/plan.md`。

## 6. 剩余工作

Phase3 见 `ref/plan.md`。Phase2 的软件接线、pytest 与 README 已完成。活 daemon 上的端到端演示还没在本环境跑（没有 orca 进程，也没有驱动栈）。

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
