# 操作日志

## 2026-10-10 01

- 动作：用上传的调研与规划文档覆盖空模板。  
  路径：`doc/专报_Orca开源中控框架调研.md`、`doc/spec/urs.md`、`doc/spec/ds.md`、`ref/intent.md`、`ref/requirement.md`、`ref/plan.md`、`ref/progress.md`。  
  影响：只替换文档，不改 `src/orca`。回滚：用 git 恢复这些路径。
- 动作：新增旁路包 `src/orca_mvc/`、前端 `web/`、测试 `tests/orca_mvc/`。  
  依赖：`pyproject.toml` 增加可选 extra `mvc`（`mcp`），以及 `orca_mvc` 的 scenario JSON 打包项。`.gitignore` 增加 `node_modules/` 与 `web/dist/`。  
  影响：不修改预约、死锁、SystemMap、daemon 路由实现。控制面默认只绑 `127.0.0.1:8100`，无认证。  
  回滚：删除上述新增路径并还原 `pyproject.toml` 与 `.gitignore`。
- 未执行：对 Orca daemon 发 HTTP；改上游内核；写入密钥或把服务绑到公网。

## 2026-10-10 02

- 动作：按评审修改同一分支。启动说明改为 `python -m orca_mvc.api` / `python -m orca_mvc.mcp_server`；`[mvc]` 收紧为 `mcp>=2,<3`；daemon 501 的 mapping 文案改为 `DAEMON_NOT_WIRED`；未知 SiLA Feature 返回 422；CORS `allow_headers` 改为 `Accept` 与 `Content-Type`。  
  影响：仍不改 `src/orca`，仍不向 daemon 发请求。  
  回滚：git 还原本次提交。
