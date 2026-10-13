"""对着已经跑起来的控制面和本机 daemon 做一次 PURE_SIM 冒烟。

前提（都在仓库根目录，见 ``src/orca_mvc/README.md``）：

1. ``orca start``
2. ``orca topology mount examples.mvc_daemon_sim:build_topology --sim``
3. 两次 ``orca workflow load``（``plate_readout`` 与 ``seal_and_shake``）
4. ``ORCA_MVC_RUNTIME=daemon`` 启动控制面

然后::

    python -m examples.mvc_daemon_sim.smoke

序列：健康检查 ``daemon_reachable``、创建并提交 ``plate_readout``、确认
``execution_ref``、列出 daemon 执行、对这条执行做两段式 stop
（``confirm=false`` 再 ``confirm=true``）。没有进程就非零退出，不会假装成功。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def _ensure_src_on_path() -> None:
    """仓库根的 ``src`` 还没装进环境时，让 ``orca_mvc`` 能被导入。"""

    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    entry = str(src)
    if src.is_dir() and entry not in sys.path:
        sys.path.insert(0, entry)


def _headers() -> dict[str, str]:
    import os

    token = os.environ.get("ORCA_MVC_API_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError:
        raise RuntimeError(
            f"HTTP {response.status_code} 不是 JSON：{response.text[:400]}"
        ) from None
    if not isinstance(body, dict):
        raise RuntimeError(f"HTTP {response.status_code} 不是对象：{body!r}")
    return body


def two_phase_stop(daemon: httpx.Client, execution_id: str) -> None:
    """与 ``OrcaDaemonBackend.cancel`` 相同的两步：先 armed，再 abort。"""

    first = daemon.post(
        "/operations/stop-execution",
        json={"execution_id": execution_id, "confirm": False},
    )
    first.raise_for_status()
    first_body = _json_object(first)
    first_status = first_body.get("status")
    print(f"stop confirm=false -> {first_status}")
    if first_status != "armed":
        phase = first_body.get("phase")
        message = first_body.get("message")
        raise RuntimeError(
            "第一段停止没有返回 armed。"
            f" status={first_status!r} phase={phase!r} message={message!r}。"
            " 执行可能已经结束或失败；动作窗口大约 "
            f"{_hold_seconds()} 秒，脚本应在提交后马上停止。"
        )
    second = daemon.post(
        "/operations/stop-execution",
        json={"execution_id": execution_id, "confirm": True},
    )
    second.raise_for_status()
    second_body = _json_object(second)
    second_status = second_body.get("status")
    print(f"stop confirm=true -> {second_status}")
    if second_status != "aborted":
        raise RuntimeError(f"第二段停止没有 abort：{second_body}")


def _hold_seconds() -> float:
    from examples.mvc_daemon_sim.specs import ACTION_HOLD_SECONDS

    return ACTION_HOLD_SECONDS


def _execution_ids(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("executions")
    if not isinstance(rows, list):
        raise RuntimeError(f"list-executions 缺少 executions：{payload!r}")
    found: list[str] = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            found.append(row["id"])
    return found


def run(api_url: str, daemon_url: str | None) -> int:
    _ensure_src_on_path()
    from orca_mvc.runtime.daemon_backend import resolve_daemon_base_url

    api = api_url.rstrip("/")
    daemon_base = (daemon_url or resolve_daemon_base_url() or "").rstrip("/")
    if not daemon_base:
        return _fail(
            "没有 daemon 地址。先在仓库根目录 orca start，"
            "或设置 ORCA_DAEMON_URL。不要假设端口 8000。"
        )

    headers = _headers()
    timeout = httpx.Timeout(30.0, connect=2.0)
    try:
        with httpx.Client(base_url=api, headers=headers, timeout=timeout) as api_client:
            health_response = api_client.get("/api/v1/health")
            if health_response.status_code == 401:
                return _fail(
                    "控制面要求 Bearer。设置与控制面相同的 ORCA_MVC_API_TOKEN。"
                )
            health_response.raise_for_status()
            health = _json_object(health_response)
            print(
                f"health runtime={health.get('runtime')!r} "
                f"daemon_reachable={health.get('daemon_reachable')!r} "
                f"daemon_url={health.get('daemon_url')!r}"
            )
            if health.get("daemon_reachable") is not True:
                return _fail(
                    "daemon_reachable 不是 true。确认 orca start 已写 daemon.json，"
                    "且控制面能访问该端口。"
                )
            if health.get("runtime") != "orca-daemon":
                return _fail(
                    "控制面执行面不是 orca-daemon。"
                    "启动时要设 ORCA_MVC_RUNTIME=daemon，当前是 "
                    f"{health.get('runtime')!r}。"
                )

            created = api_client.post(
                "/api/v1/tasks",
                json={
                    "name": "PURE_SIM plate_readout",
                    "protocol_ref": "plate_readout",
                    "workcell_id": "cell_a",
                },
            )
            if created.status_code != 201:
                return _fail(f"创建任务失败 HTTP {created.status_code}：{created.text}")
            task_id = _json_object(created).get("id")
            if not isinstance(task_id, str) or not task_id:
                return _fail(f"创建任务响应没有 id：{created.text}")

            submitted = api_client.post(f"/api/v1/tasks/{task_id}/submit")
            if submitted.status_code != 200:
                return _fail(f"提交失败 HTTP {submitted.status_code}：{submitted.text}")
            submitted_body = _json_object(submitted)
            execution_ref = submitted_body.get("execution_ref")
            if not isinstance(execution_ref, str) or not execution_ref:
                return _fail(f"提交响应没有 execution_ref：{submitted.text}")
            print(f"submitted task={task_id} execution_ref={execution_ref}")

            with httpx.Client(base_url=daemon_base, timeout=timeout) as daemon_client:
                listed = daemon_client.get("/operations/list-executions")
                listed.raise_for_status()
                ids = _execution_ids(_json_object(listed))
                if execution_ref not in ids:
                    return _fail(
                        f"list-executions 里没有 {execution_ref}。当前 id：{ids}"
                    )
                print(f"list-executions 含 {execution_ref}（共 {len(ids)} 条）")
                two_phase_stop(daemon_client, execution_ref)
                cleared = daemon_client.post(
                    "/labware/runtime/clear-all", json={"force": True}
                )
                if cleared.status_code != 200:
                    raise RuntimeError(
                        "两段式停止已经完成，但清场失败 "
                        f"HTTP {cleared.status_code}：{cleared.text[:400]}。"
                        "板还在 pad 上时，下一次提交会 409 start_location_occupied。"
                        "可再执行 orca labware clear-all --yes。"
                    )
                print(f"clear-all -> {cleared.text[:200]}")

            deadline_status = "cancelled"
            observed = None
            for _ in range(20):
                current = api_client.get(f"/api/v1/tasks/{task_id}")
                current.raise_for_status()
                observed = _json_object(current).get("status")
                if observed == deadline_status:
                    break
                time.sleep(0.25)
            print(f"control-plane task status={observed}")
            if observed != deadline_status:
                return _fail(
                    "daemon 已 abort，但控制面任务没有在轮询里变成 cancelled。"
                    f" 最后状态 {observed!r}。"
                )
    except httpx.HTTPError as exc:
        return _fail(f"HTTP 失败：{exc}")
    except RuntimeError as exc:
        return _fail(str(exc))
    print("smoke ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(
        description="本机 daemon + 控制面的 PURE_SIM 冒烟。"
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("ORCA_MVC_API_URL", "http://127.0.0.1:8100"),
        help="控制面根地址，默认 ORCA_MVC_API_URL 或 http://127.0.0.1:8100",
    )
    parser.add_argument(
        "--daemon-url",
        default=None,
        help="覆盖 daemon 地址。默认 ORCA_DAEMON_URL，否则读 daemon.json 的 port",
    )
    args = parser.parse_args(argv)
    return run(args.api_url, args.daemon_url)


if __name__ == "__main__":
    raise SystemExit(main())
