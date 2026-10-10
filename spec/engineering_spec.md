# 工程与开发规范

覆盖设计、编码、环境、依赖、构建、测试、部署与版本管理。细则可参考同目录其他规范文件。

参考：
- [Twelve-Factor App](https://12factor.net/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Google Engineering Practices](https://google.github.io/eng-practices/)

## 设计

- 先厘清边界与接口，再写实现；变更先评估影响面与回滚方式。
- 默认单体模块化 + 稳定接口；设备 / DB 经适配层接入。
- 小步交付：一次变更聚焦一件事（对齐 Google：Small CLs）。

## 编码

- 遵循 `coding_standards.md`。
- 新增 / 修改逻辑时同步考虑测试与文档；不引入“将来可能用到”的抽象。
- 公开 API、设备协议、配置 schema 变更视为契约变更，需更新约定与调用方。

## 环境与依赖

- 使用项目约定的环境工具（默认 `uv`，见 `tech_stack.md`）。
- 依赖显式声明并锁定版本；生产与开发隔离方式一致。
- 新增依赖需说明用途，优先维护活跃、许可证清晰的库。

## 构建与运行

- 提供可复现的安装 / 启动命令（README 或 `technical_manual.md`）。
- 构建产物、缓存不入库；本地路径不写死，用配置或环境变量。
- 跨平台路径与脚本注意可移植性。

## 测试与质量

- 遵循 `testing_quality.md`。
- 有行为变更的改动应附带相应测试；重构前尽量有基线测试。
- 提交前至少跑通与本次改动相关的检查（lint / 单测 / 关键冒烟）。

## 部署

- 配置与密钥外置；环境差异不进代码。
- 容器部署时保持镜像可复现、健康检查与日志可观测（见 `observability.md`）。
- 生产变更需可回滚；高风险操作先确认用户。

## Git 版本管理（如适用）

### 基本原则

- 行动前确认分支与状态：`git status` / `git branch`。
- 破坏性操作（`reset --hard`、`push --force`、`rebase`、删分支等）前评估风险、向用户确认，并记入操作日志。
- 不擅自 `push`，除非用户明确要求。

### 分支策略

遵循现有项目规范；若无，建议：

| 分支 | 用途 |
|------|------|
| `main` / `master` | 稳定可发布 |
| `develop` | 集成开发（可选） |
| `feature/<描述>` | 新功能 |
| `fix/<描述>` | 缺陷修复 |
| `hotfix/<描述>` | 紧急修复 |
| `refactor/<描述>` | 重构 / 改造 |

二开、改造在独立分支进行，避免直接污染主分支。

### 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
<type>(<scope>): <subject>
```

常用 type：`feat`、`fix`、`docs`、`refactor`、`test`、`chore`、`perf`、`build`、`ci`。

示例：`feat(gateway): 新增 Modbus 设备适配层`

- 一次提交聚焦一件事；中英文与项目现有风格一致。
- 破坏性变更用 `!` 或 `BREAKING CHANGE` 脚注标明。

### .gitignore

忽略：虚拟环境（`.venv/`、`venv/`）、缓存（`__pycache__/`、`node_modules/`）、构建产物、日志、密钥 / 凭证、本地配置、大文件等。

敏感信息严禁入库；用 `.env`（并忽略）或密钥管理方案。

### 其他

- 大文件 / 二进制 / 模型权重：评估 Git LFS 或外部存储。
- 合并冲突先理解再解决，必要时与用户确认。
