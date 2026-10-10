# 编码规范

在遵循项目已有风格的前提下，采用下列默认约定。语言专项指南可覆盖本文件对应条款。

参考：
- [PEP 8](https://peps.python.org/pep-0008/) / [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- [Google Engineering Practices — Code Review](https://google.github.io/eng-practices/review/)

## 命名与结构

- 名称表达含义；避免无意义缩写。Python：`snake_case`；类型 / 类：`PascalCase`。TS：变量 / 函数 `camelCase`，类型 / 组件 `PascalCase`。
- 目录按职责分层（如 `api` / `domain` / `adapters` / `config`），与架构一致。
- 单文件职责清晰；过长文件优先按模块拆分，而非堆砌工具函数。

## 类型与接口

- Python：公共函数与关键数据结构补类型注解；对外 API 尽量完整。
- TypeScript：开启严格模式相关选项（如 `strict`）；避免随意 `any`。
- 跨模块边界用明确接口 / Protocol / 抽象基类，而不是依赖具体实现细节。

## 格式与静态检查

- 使用项目约定的 formatter / linter（如 Python：`ruff` / `black`；TS：`eslint` / `prettier`）。
- 提交前格式化；不混入与功能无关的大范围格式化 diff。

## 注释与文档

- 注释写「为什么」，少写「做了什么」。
- 公共模块、适配层、配置项补充简短说明或 docstring。
- 行为或契约变更时同步更新 README / 相关 `spec` / 技术说明。

## 错误处理

- 不吞异常；捕获后记录上下文并向上抛出或转换为领域错误。
- 对外部系统（设备、网络、DB）显式处理超时、重试与失败语义（见 `observability.md`、`interface_contracts.md`）。

## 禁止与谨慎

- 不提交密钥、绝对本地路径、调试残留（`print` 刷屏、临时硬编码）。
- 不引入未使用依赖；不复制粘贴后遗留死代码。
- 并发 / 硬件控制代码优先简单可推理模型，复杂锁与全局状态需书面理由。
