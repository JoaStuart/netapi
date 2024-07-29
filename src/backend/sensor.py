from abc import ABC, abstractmethod
import logging
import os
import time
import traceback
from typing import Any, Type
from backend.output import OutputDevice
from device.pluginloader import load_plugins
from locations import PL_SENSOR

LOG = logging.getLogger()


class Sensor(ABC):
    def __init__(self, repoll_after: float = 5) -> None:
        self.data: dict[str, Any] = {}
        self._last_poll = 0
        self._repoll_after = repoll_after

    def tpoll(self) -> None:
        if time.time() < self._last_poll + self._repoll_after:
            self.poll()

    @abstractmethod
    def poll(self) -> None:
        """Polls data from the attached sensor

        [Needs to be implemented by the sensor!]
        """
        raise NotImplementedError()

    @abstractmethod
    def to(self, device: OutputDevice) -> None:
        """Feeds the data of the current sensor into the given `OutputDevice`

        Args:
            device (OutputDevice): Device to feed into
        """
        raise NotImplementedError()

    @abstractmethod
    def __str__(self) -> str | None:
        """Stringifies the read sensor value. If no data has been polled yet, return `None`

        Returns:
            str: String containing read values
        """
        raise NotImplementedError()


SENSORS: dict[str, Type[Sensor]] = load_plugins(PL_SENSOR, Sensor)
