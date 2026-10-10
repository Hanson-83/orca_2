# 技术栈与环境

本文件约定默认技术选型与运行环境。项目另有说明或二开改造时，优先遵循原项目技术栈。

参考：[Twelve-Factor App](https://12factor.net/)（依赖隔离、配置外置、后端服务可替换）

## 操作系统

- 主环境：Ubuntu；需兼顾其他 Linux 发行版的可迁移性（路径、包管理、systemd 等差异需评估）。
- 涉及 Windows / macOS 时，事先评估兼容性与 CI 覆盖范围，避免隐式依赖特定 OS API。

## 编程语言

无特别说明时优先级：

1. Python
2. TypeScript
3. 适配现有项目源码所用语言

已有项目二开 / 改造：优先遵循并适配原项目语言与技术栈。

## 前端

- 默认：TypeScript + 成熟框架（React / Vue）。
- 简单原型 / Demo：Python + Tkinter。
- 较复杂桌面应用：Python + PySide / PyQt。
- 选型原则：成熟、长期维护、易部署、轻量。

## 后端

- 默认：Python。
- 优先成熟、长期维护、易部署、轻量的框架（如 FastAPI / Flask）。
- 依赖与配置显式声明；不依赖“机器上碰巧装了”的全局包（见 Twelve-Factor：Dependencies）。

## 前后端协作

- 默认前后端分离。
- 采用成熟结构（如 MVC / MVVM）解耦，使同一后端可适配多个前端。
- 接口以稳定契约为准（见 `interface_contracts.md`）。

## 架构

- 采用分层、模块化、组件化解耦；默认优先**单体模块化**，避免过早微服务化。
- 模块之间、层与层之间通过稳定接口通信。
- 数据库连接与硬件设备连接：优先「网关 / 适配层」，解耦业务逻辑与具体驱动 / 存储实现，便于替换与扩展（对齐 Twelve-Factor：Backing Services）。

## 设计模式

- 按问题选型（如 Strategy、Adapter、Factory、Observer 等），解决真实痛点。
- 避免过度设计与过早抽象；新增抽象须有明确复用或替换动机。

## 可配置性

- 易变部分从代码抽离：设备类型与参数、远端接口、工作流、任务序列等。
- 运行时通过配置文件或命令行参数注入。
- 配置文件优先 YAML；若项目已有格式则沿用。
- 密钥与部署差异项不写死在代码中（见 `security.md`、Twelve-Factor：Config）。

## 虚拟与隔离环境

- Python 默认：`uv` 管理虚拟环境与依赖；其次 `conda`。
- 原项目 README / 文档已指定工具时，优先遵循原说明。
- 依赖清单锁定（如 `uv.lock` / `requirements.txt` 精确版本），保证可复现。
- 容器化可用 Docker / Docker Compose，镜像与 compose 文件纳入版本管理。
