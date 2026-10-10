# 意图文档（intent.md）

> 路径约定：仓库内为 `ref/intent.md`。本文件为 orca_2「MVC 扩展」本轮意图。  
> 更新日期：2026-10-10

## 1. 来源

用户在本地 fork `D:\Projects\orca_2`（GitHub: https://github.com/Hanson-83/orca_2）上，基于开源实验室自动化中控框架 Orca（https://github.com/Cheshire-Labs/orca ，官网 https://cheshirelabs.io/），要求：

1. 详细调研 Orca 架构、模型、分层、模块、调度、路径规划、任务到驱动链路，并与 VWorks 概念对照；  
2. 在其基础上实现扩展：多实验任务平行运行与管理、多 workcell 集群工作流、SiLA2 与 ROS2 接口集成、基于 API 的 MCP Server、前后端分离的 Web 前端；  
3. 按仓库 AGENTS.md 文档体系推进；可先云端工作，多智能体协同（统筹/开发/审核）。

## 2. 宏观目标

把 Orca 从「单机 localhost 工作流引擎」推进为可支撑 **实验室集群控制面** 的可扩展底座：业务侧能并行管理多个实验任务，拓扑侧能描述多个 workcell，集成侧能对接 SiLA2/ROS2/MCP/Web，且 **不破坏上游 `src/orca` 核心调度与预约内核**。

## 3. 范围（本轮要做）

- 调研专报与 URS/DS/计划文档齐全；  
- Phase1：**MVC 扩展骨架**可运行最小闭环（任务并行、双 cell 拓扑、适配器 stub、MCP tools、独立前端、pytest、启动说明）。

## 4. 边界（本轮不做或降级）

- 不重写 Orca 预约/死锁内核；  
- SiLA2/ROS2 不接真机，仅契约 + mock；  
- MCP/前端不做完整生产级鉴权（须在文档标明风险与后续）；  
- 不做全局 makespan 最优调度器（可列为后续）；  
- 不修改上游许可与 CLA 相关法律文本。

## 5. 成功的粗略样子

开发者按 README 能拉起控制面 + 前端；可提交两个实验任务并看到状态；可查看双 workcell 拓扑；MCP 可 list/submit/get_status；测试通过；文档链完整可指导下一阶段深化。
