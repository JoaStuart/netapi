import abc

from device.device import Device


class PermissionLevel(abc.ABC):
    @abc.abstractmethod
    def int_level(self) -> int:
        pass

    @abc.abstractmethod
    def device(self) -> Device | None:
        pass


class DefaultPermissions(PermissionLevel):
    def int_level(self) -> int:
        return 0

    def device(self) -> None:
        return None


class SubdevPermissions(PermissionLevel):
    def __init__(self, device: Device) -> None:
        self._device = device

    def int_level(self) -> int:
        return 50

    def device(self) -> Device:
        return self._device


class MaxPermissions(PermissionLevel):
    def __init__(self, device: Device) -> None:
        self._device = device

    def int_level(self) -> int:
        return 100

    def device(self) -> Device:
        return self._device
