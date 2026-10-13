"""本机 PURE_SIM 冒烟用的固定名字。

这里不导入 orca。控制面测试可以读这些字符串，而不拉起驱动栈。
daemon 每次 ``orca workflow load`` 只注册一个 WorkflowTemplate，所以两条协议
各有一个 ``module:build_workflow``。
"""

from __future__ import annotations

TOPOLOGY_SPEC = "examples.mvc_daemon_sim:build_topology"
PLATE_READOUT_SPEC = "examples.mvc_daemon_sim.plate_readout:build_workflow"
SEAL_AND_SHAKE_SPEC = "examples.mvc_daemon_sim.seal_and_shake:build_workflow"

PLATE_READOUT_WORKFLOW = "plate_readout"
SEAL_AND_SHAKE_WORKFLOW = "seal_and_shake"

# 动作末尾的等待。给控制面提交之后的 list / 两段式 stop 留出窗口，单位秒。
ACTION_HOLD_SECONDS = 8.0
