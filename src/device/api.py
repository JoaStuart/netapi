import logging
from abc import ABC, abstractmethod
from sre_constants import SUCCESS
from typing import Any, Optional, Type

from backend.interval import (
    DailyExecutor,
    DeferredExecutor,
    Executor,
    TimedExecutor,
    UnixExecutor,
)
from device.pluginloader import load_plugins
from locations import PL_BFUNC
from utils import dumpb
from webserver.webrequest import WebRequest, WebResponse


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
    def api(self) -> "APIResult":
        """Execute the API function

        Returns:
            APIResult: The result of the API function
        """

        pass


class APIResult:
    @staticmethod
    def by_msg(message: str, success: bool = True) -> "APIResult":
        return APIResult(success, json=message)

    @staticmethod
    def by_success(success: bool) -> "APIResult":
        return APIResult(success)

    @staticmethod
    def by_json(json: dict | Any, success: bool = True) -> "APIResult":
        return APIResult(success, json=json)

    @staticmethod
    def by_data(data: bytes, mime: str, success: bool = True) -> "APIResult":
        return APIResult(success, data=(data, mime))

    @staticmethod
    def empty() -> "APIResult":
        return APIResult(True, json={})

    def __init__(
        self,
        success: bool,
        json: Optional[dict | Any] = None,
        data: Optional[tuple[bytes, str]] = None,
    ) -> None:
        self._success = success
        self._json_data = json
        self._raw_data = data

    def combine(self, api_name: str, other: "APIResult") -> None:
        self._success &= other.success

        if other.json != None and isinstance(self._json_data, dict):
            self._json_data[api_name] = other.json

        if other.data != None:
            self._raw_data = other.data

    @property
    def success(self) -> bool:
        return self._success

    @property
    def json(self) -> Optional[dict | Any]:
        return self._json_data

    @json.setter
    def set_json(self, json: dict) -> None:
        self._json_data = json

    @property
    def data(self) -> Optional[tuple[bytes, str]]:
        return self._raw_data

    @data.setter
    def set_data(self, data: tuple[bytes, str]) -> None:
        self._raw_data = data

    def webresponse(self, headers: dict[str, str] = {}) -> WebResponse:
        code = 200 if self._success else 500
        msg = "OK" if self._success else "NOK"

        if self._raw_data != None:
            return WebResponse(code, msg, headers=headers, body=self._raw_data)
        elif isinstance(self._json_data, dict):
            return WebResponse(code, msg, headers=headers, body=dumpb(self._json_data))
        else:
            return WebResponse(
                code,
                msg,
                headers=headers,
                body=(str(self._json_data).encode(), "text/plain"),
            )


def load_dir(dir: str) -> dict[str, Type[APIFunct]]:
    pl = load_plugins(dir, [APIFunct, Executor])

    tasks = pl[Executor]
    for name, task in tasks.items():
        LOG.debug("Registering task %s", name)

        if (
            task != TimedExecutor
            and task != DeferredExecutor
            and task != UnixExecutor
            and task != DailyExecutor
        ):
            task()

    return pl[APIFunct]
