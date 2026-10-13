"""一块板位、一台读板机、一台封膜机、一台振荡器、一条机械臂。

给 ``orca topology mount examples.mvc_daemon_sim:build_topology --sim`` 用。
不依赖 ``tests.test_helpers``。

daemon 挂载时外层绑定的是 ``RemoteDeviceFactory``。这套夹具在构造设备时改绑
``SimDeviceFactory``，live 槽和 sim 槽都是进程内 Sim*，不需要设备桥。
``sim_override=PURE_SIM`` 再挡一层：误提交 ``LIVE`` 也不会改走真机。
"""

from __future__ import annotations

from cheshire_drivers import AccessConfig, CartesianCoordinates, Teachpoint

from orca.devices.devices import Reader
from orca.devices.sealer import Sealer
from orca.devices.shaker import Shaker
from orca.resource_models.plate_pad import PlatePad
from orca.resource_models.transporter import Transporter
from orca.runtime.device_factory import SimDeviceFactory
from orca.runtime.device_factory_context import use_device_factory
from orca.runtime.run_modes import WorkflowRunMode
from orca.runtime.store_factory import IRuntimeStoreFactory
from orca.sdk.build import Topology


def build_topology(stores: IRuntimeStoreFactory) -> Topology:
    """每次调用都新建一套对象。daemon 从 ``orca start`` 的工作目录导入本模块。"""

    default_vertical = AccessConfig(name="default_vertical", access_type="vertical")
    stores.access_configs(seed=[default_vertical])

    # 关键字对齐 CartesianCoordinates(x, y, z, yaw, pitch, roll)。
    # 垂直取放用 pitch=90、yaw=180，和 daemon 测试夹具里的示教点同一组姿态。
    def _point(name: str, x: float) -> Teachpoint:
        return Teachpoint(
            name,
            CartesianCoordinates(x=x, y=0.0, z=50.0, yaw=180.0, pitch=90.0, roll=0.0),
            orientation="right",
            access=default_vertical,
        )

    teachpoints = [
        _point("pad", 100.0),
        _point("reader", 250.0),
        _point("sealer", 400.0),
        _point("shaker", 550.0),
    ]

    with use_device_factory(SimDeviceFactory()):
        reader = Reader("reader", sim_override=WorkflowRunMode.PURE_SIM)
        sealer = Sealer("sealer", sim_override=WorkflowRunMode.PURE_SIM)
        shaker = Shaker("shaker", sim_override=WorkflowRunMode.PURE_SIM)
        robot = Transporter(
            "robot",
            teachpoint_store=stores.teachpoints("robot", seed=teachpoints),
            sim_override=WorkflowRunMode.PURE_SIM,
        )

    return Topology(
        locations={
            "pad": PlatePad("pad"),
            "reader": reader,
            "sealer": sealer,
            "shaker": shaker,
        },
        transporters=[robot],
    )
