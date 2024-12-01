import logging
from abc import ABC, abstractmethod
from typing import Any, Type

from backend.interval import Executor
from device.pluginloader import load_plugins
from locations import PL_BFUNC
from webserver.webrequest import WebRequest


LOG = logging.getLogger()


class APIFunct(ABC):
    def __init__(
        self, request: WebRequest | None, args: list[str], body: dict[str, Any]
    ) -> None:
        self.request = request
        self.args = args
        self.body = body

    def permissions(self, default: int) -> int:
        return default

    @abstractmethod
    def api(self) -> dict | tuple[bytes, str]:
        """Execute the API function

        Returns:
            dict | tuple[bytes, str]: A JSON response or a bytes body with a mime type
        """

        pass


def load_dir(dir: str) -> dict[str, Type[APIFunct]]:
    pl = load_plugins(dir, [APIFunct, Executor])

    tasks = pl[Executor]
    for name, task in tasks.items():
        LOG.debug("Registering task %s", name)
        task()

    return pl[APIFunct]
