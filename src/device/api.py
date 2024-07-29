import logging
from abc import ABC, abstractmethod
from typing import Any, Type

from device.pluginloader import load_plugins
from locations import PL_BFUNC
from webserver.webrequest import WebRequest


LOG = logging.getLogger()


class APIFunct(ABC):
    def __init__(
        self, request: WebRequest, args: list[str], body: dict[str, Any]
    ) -> None:
        self.request = request
        self.args = args
        self.body = body

    @abstractmethod
    def api(self) -> dict | tuple[bytes, str]:
        """Execute the API function

        Returns:
            dict | tuple[bytes, str]: A JSON response or a bytes body with a mime type
        """
        pass


def load_dir(dir: str) -> dict[str, Type[APIFunct]]:
    return load_plugins(PL_BFUNC, APIFunct)
