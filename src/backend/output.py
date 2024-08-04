import logging
from abc import ABC, abstractmethod
from typing import Any, Type

from device.pluginloader import load_plugins
from locations import PL_OUTPUT


LOG = logging.getLogger()


class OutputDevice(ABC):
    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self.data = data

    @abstractmethod
    def api_resp(self) -> dict:
        """Generates the contents for the API response for the device to consume

        Returns:
            dict: A dictionary that gets or'd to the API response
        """
        pass

    def api_headers(self) -> dict[str, str]:
        return {}

    def api_response(self, orig: tuple[int, str]) -> tuple[int, str]:
        """Response code and message for the api request

        Args:
            orig (tuple[int, str]): Original response

        Returns:
            tuple[int, str]: Response after changes from this api call
        """
        return orig


class DefaultOutput(OutputDevice):
    def api_resp(self) -> dict:
        return {k: str(v) for k, v in self.data.items()}


do: dict[str, Type[OutputDevice]] = {"default": DefaultOutput}
OUTPUTS: dict[str, Type[OutputDevice]] = do | load_plugins(PL_OUTPUT, OutputDevice)
