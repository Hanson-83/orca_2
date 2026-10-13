"""``seal_and_shake``：封一下膜，再短振，然后停住几秒。

入口：``examples.mvc_daemon_sim.seal_and_shake:build_workflow``。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import orca.orca as orca
from orca.devices.sealer import Sealer
from orca.devices.shaker import Shaker
from orca.runtime.sim_labware import SimPlateTemplate
from orca.sdk.build import Topology
from orca.sdk.workflow import MethodTemplate
from orca.workflow_models.action_context import ActionContext
from orca.workflow_models.action_template import ActionTemplate
from orca.workflow_models.method_context import MethodContext
from orca.workflow_models.thread_context import ThreadContext
from orca.workflow_models.workflow_context import WorkflowContext
from orca.workflow_models.workflow_templates import WorkflowTemplate

from examples.mvc_daemon_sim.specs import ACTION_HOLD_SECONDS, SEAL_AND_SHAKE_WORKFLOW


def build_workflow(topology: Topology) -> WorkflowTemplate:
    """登记名字正好是 ``seal_and_shake`` 的模板。"""

    plate = SimPlateTemplate("seal_plate")
    sealer = topology.device("sealer", Sealer)
    shaker = topology.device("shaker", Shaker)

    @orca.action(device=sealer, inputs=[plate])
    async def seal_plate(ctx: ActionContext) -> None:
        await ctx.device().seal(temperature=100, duration=1)

    @orca.action(device=shaker, inputs=[plate])
    async def shake_plate(ctx: ActionContext) -> None:
        await ctx.device().shake(duration=1, speed=500)
        await asyncio.sleep(ACTION_HOLD_SECONDS)

    @orca.method
    async def seal_then_shake(
        ctx: MethodContext,
    ) -> AsyncGenerator[ActionTemplate, None]:
        del ctx
        yield seal_plate
        yield shake_plate

    @orca.thread(labware=plate, start="pad", end="pad")
    async def seal_journey(ctx: ThreadContext) -> AsyncGenerator[MethodTemplate, None]:
        del ctx
        yield seal_then_shake

    @orca.workflow(name=SEAL_AND_SHAKE_WORKFLOW)
    def seal_and_shake(wf: WorkflowContext) -> None:
        wf.start(seal_journey)

    return seal_and_shake
