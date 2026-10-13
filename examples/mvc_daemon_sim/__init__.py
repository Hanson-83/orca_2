"""本机 daemon 的 PURE_SIM 夹具：``plate_readout`` 与 ``seal_and_shake``。

``import examples.mvc_daemon_sim`` 不会加载 orca。``build_topology`` 在第一次
被访问（``orca topology mount examples.mvc_daemon_sim:build_topology``）时才导入。

命令见 ``src/orca_mvc/README.md``。冒烟：``python -m examples.mvc_daemon_sim.smoke``。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_plate_readout",
    "build_seal_and_shake",
    "build_topology",
]


def __getattr__(name: str) -> Any:
    if name == "build_topology":
        from examples.mvc_daemon_sim.topology import build_topology

        return build_topology
    if name == "build_plate_readout":
        from examples.mvc_daemon_sim.plate_readout import (
            build_workflow as build_plate_readout,
        )

        return build_plate_readout
    if name == "build_seal_and_shake":
        from examples.mvc_daemon_sim.seal_and_shake import (
            build_workflow as build_seal_and_shake,
        )

        return build_seal_and_shake
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
