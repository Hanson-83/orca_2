# spec 目录说明

本目录存放可复用的工程规范，供 `AGENTS.md` 及 Cursor / Claude Code / Codex / Hermes 等智能体引用。

| 文件 | 用途 |
|------|------|
| `tech_stack.md` | 技术选型与运行环境 |
| `engineering_spec.md` | 设计 / 构建 / 测试 / 部署 / Git 等工程规范 |
| `coding_standards.md` | 编码风格与静态质量 |
| `testing_quality.md` | 测试策略与完成定义 |
| `security.md` | 密钥、权限与依赖安全 |
| `observability.md` | 日志、错误处理与可观测性 |
| `interface_contracts.md` | API / DB / 设备适配层契约 |

使用方式：智能体在相关任务中优先阅读本目录对应文件；项目级特例写在项目 README 或 `ref/` 文档中并覆盖默认约定。
