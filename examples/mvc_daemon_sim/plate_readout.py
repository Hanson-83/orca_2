"""``plate_readout``：读一次板，然后短暂停住，方便两段式停止。

``orca workflow load`` 一次只登记一个模板，所以本函数单独作为一个入口：
``examples.mvc_daemon_sim.plate_readout:build_workflow``。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import orca.orca as orca
from orca.devices.devices import Reader
from orca.runtime.sim_labware import SimPlateTemplate
from orca.sdk.build import Topology
from orca.sdk.workflow import MethodTemplate
from orca.workflow_models.action_context import ActionContext
from orca.workflow_models.action_template import ActionTemplate
from orca.workflow_models.method_context import MethodContext
from orca.workflow_models.thread_context import ThreadContext
from orca.workflow_models.workflow_context import WorkflowContext
from orca.workflow_models.workflow_templates import WorkflowTemplate

from examples.mvc_daemon_sim.specs import ACTION_HOLD_SECONDS, PLATE_READOUT_WORKFLOW


def build_workflow(topology: Topology) -> WorkflowTemplate:
    """登记名字正好是 ``plate_readout`` 的模板。"""

    plate = SimPlateTemplate("readout_plate")
    reader = topology.device("reader", Reader)

    @orca.action(device=reader, inputs=[plate])
    async def read_plate(ctx: ActionContext) -> None:
        await ctx.device().read("plate_readout.pro", "plate_readout.csv")
        await asyncio.sleep(ACTION_HOLD_SECONDS)

    @orca.method
    async def read_plate_method(
        ctx: MethodContext,
    ) -> AsyncGenerator[ActionTemplate, None]:
        del ctx
        yield read_plate

    @orca.thread(labware=plate, start="pad", end="pad")
    async def readout_journey(
        ctx: ThreadContext,
    ) -> AsyncGenerator[MethodTemplate, None]:
        del ctx
        yield read_plate_method

    @orca.workflow(name=PLATE_READOUT_WORKFLOW)
    def plate_readout(wf: WorkflowContext) -> None:
        wf.start(readout_journey)

    return plate_readout
