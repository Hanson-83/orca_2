"""适配器包。默认 sim 走可测协议；mock 仍保留为纯内存实现。"""

from orca_mvc.adapters.base import (
    AdapterOffline,
    Ros2Adapter,
    Sila2Adapter,
    UnknownSilaCommand,
    UnknownSilaFeature,
)
from orca_mvc.adapters.ros2_mock import Ros2MockAdapter
from orca_mvc.adapters.ros2_sim import Ros2SimAdapter
from orca_mvc.adapters.sila2_mock import Sila2MockAdapter
from orca_mvc.adapters.sila2_sim import Sila2SimAdapter

__all__ = [
    "AdapterOffline",
    "Ros2Adapter",
    "Ros2MockAdapter",
    "Ros2SimAdapter",
    "Sila2Adapter",
    "Sila2MockAdapter",
    "Sila2SimAdapter",
    "UnknownSilaCommand",
    "UnknownSilaFeature",
]
