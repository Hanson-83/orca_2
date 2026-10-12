"""可选：本机已经 orca start 时探一次 GET /health。没有进程就跳过。"""

from __future__ import annotations

import httpx
import pytest

from orca_mvc.runtime.daemon_backend import resolve_daemon_base_url


def test_optional_live_daemon_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    url = resolve_daemon_base_url()
    if not url:
        pytest.skip("没有 ORCA_DAEMON_URL，也没有 ~/.orca/daemon.json")
    try:
        response = httpx.get(f"{url}/health", timeout=0.4)
    except httpx.HTTPError as exc:
        pytest.skip(f"orca daemon 未在运行：{exc}")
    if response.status_code != 200:
        pytest.skip(f"daemon /health 返回 {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        pytest.skip("daemon /health 不是 JSON")
    if not isinstance(body, dict) or body.get("daemon") != "ok":
        pytest.skip("该地址不是 Orca daemon")
    assert body["daemon"] == "ok"
