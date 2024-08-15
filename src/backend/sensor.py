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
    polling = False
    _last_poll = 0

    def __init__(self, repoll_after: float = 5) -> None:
        self.data: dict[str, Any] | None = None
        self._repoll_after = repoll_after

    def tpoll(self) -> None:
        """Polls the data using the interval set by the sensor"""

        if not self.polling:
            LOG.debug("Starting poll")
            self.polling = True
            if time.time() > self._last_poll + self._repoll_after:
                LOG.debug("Poll vars")
                self.poll()
                self._last_poll = time.time()
            self.polling = False
        else:
            LOG.debug("Falling into wait loop")
            while self.polling:
                time.sleep(0.1)

    @abstractmethod
    def poll(self) -> None:
        """Polls data from the attached sensor"""

        pass

    @abstractmethod
    def to(self, device: OutputDevice, args: list[str]) -> None:
        """Feeds the data of the current sensor into the given `OutputDevice`

        Args:
            device (OutputDevice): Device to feed into
        """

        pass

    @abstractmethod
    def __str__(self) -> str | None:
        """Stringifies the read sensor value. If no data has been polled yet, return `None`

        Returns:
            str: String containing read values
        """

        pass


SENSORS: dict[str, Sensor] = {
    k: v() for k, v in load_plugins(PL_SENSOR, Sensor).items()
}
