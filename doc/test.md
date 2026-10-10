# 测试与验证记录

## 2026-10-10 Phase 1 控制面

环境：Python 3.12。未安装完整 `cheshire-orca` 与驱动栈。控制面依赖 FastAPI / httpx / pydantic / pytest / pytest-asyncio / pytest-timeout，以及可选的 `mcp` 2.3.0。

### pytest

```bash
python -m pytest tests/orca_mvc --confcutdir=tests/orca_mvc
```

结果：14 passed。覆盖并行任务与状态查询、取消、双 cell 拓扑、跨 cell 转运占位、SiLA2/ROS2 mock、MCP `submit_task` 返回任务 id、daemon 路由与源码一致且 Phase 1 不发出请求。

未跑上游全量 `pytest tests`：当前环境没有安装 `orca` 本体，且那次运行不在本阶段范围内。

### 前端构建

```bash
cd web && npm install && npm run build
```

结果：`tsc --noEmit` 与 `vite build` 通过。

### 手工冒烟

`PYTHONPATH=src python -m orca_mvc.api` 监听 `127.0.0.1:8100`，`web` 下 `npm run dev` 监听 `127.0.0.1:5173`。`GET /api/v1/health` 返回 `runtime=mock`、`auth=none`。

浏览器打开前端后核对：

- 页面无连接错误；Workcell A / B 显示为空闲。
- 提交「下午读板」到 cell_a 后，任务表出现该行，执行引用以 `mock-` 开头，状态到达「已完成」。默认时间线大约 0.8 秒，这次观察没有截到「忙碌」，并行 running 由 pytest 断言。
- 「模拟 SiLA2 调用」后计数变为 1，日志含 `ShakerControl` / `Shake`。
- 从 cell_a 到 cell_b 请求 `plate-demo`，状态到达「已到达」。
- 约 1280px 为双栏，约 390px 折成单栏，没有截断到不可用。
