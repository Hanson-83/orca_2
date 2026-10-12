"""设备适配器契约。mock 是纯内存；sim 走可测协议，仍然没有硬件。"""

from typing import Protocol


class AdapterOffline(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"{name} adapter is offline")


class UnknownSilaFeature(Exception):
    """目录里没有这个 Feature。控制面把它收成 422。"""

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(f"unknown SiLA2 feature: {feature}")


class UnknownSilaCommand(Exception):
    def __init__(self, feature: str, command: str) -> None:
        self.feature = feature
        self.command = command
        super().__init__(f"unknown SiLA2 command: {feature}/{command}")


class Sila2Adapter(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def list_features(self) -> list[str]: ...

    async def call_command(self, feature: str, command: str, params: dict) -> dict: ...

    def health(self) -> dict: ...


class Ros2Adapter(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def list_topics(self) -> list[str]: ...

    async def publish(self, topic: str, message: dict) -> None: ...

    async def call_service(self, service: str, request: dict) -> dict: ...

    def health(self) -> dict: ...
