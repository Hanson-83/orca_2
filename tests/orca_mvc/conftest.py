"""把 src 放进导入路径，这样不必先安装整包。

仓库根目录的 tests/conftest.py 会导入上游 orca。本目录的用例只覆盖控制面，
运行时加 ``--confcutdir=tests/orca_mvc``，避免去加载那个 conftest。
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest_asyncio

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from orca_mvc.api.app import create_app
from orca_mvc.services.control_plane import ControlPlane


@pytest_asyncio.fixture
async def plane() -> ControlPlane:
    control = ControlPlane(
        step_delay=0.05,
        running_hold=0.8,
        poll_interval=0.02,
        transfer_step=0.05,
    )
    await control.startup()
    try:
        yield control
    finally:
        await control.shutdown()


@pytest_asyncio.fixture
async def client(plane: ControlPlane):
    app = create_app(plane)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
