import logging
import os
import sys
import time

import locations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from device.device import FrontendDevice


_log_formatter = logging.Formatter(
    "%(asctime)s :: %(funcName)s<@>%(threadName)s [%(levelname)-1.1s] %(message)s",
    "%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger()


class HttpLogger(logging.Handler):
    def __init__(self, ip: str, port: int, device: "FrontendDevice") -> None:
        self._ip = ip
        self._port = port
        self._token = device._token

    def emit(self, record: logging.LogRecord) -> None:
        from webclient.client_request import WebClient, WebMethod

        try:
            log_entry = self.format(record)
            log_json = {
                "level": record.levelname,
                "message": log_entry,
            }

            if record.exc_text:
                log_json["exception"] = record.exc_text

            WebClient(self._ip, self._port).set_path("/log").set_secure(
                True
            ).set_method(WebMethod.POST).authorize(self._token).set_json(
                log_json
            ).send()
        except Exception as e:
            print(f"Failed to send log: {e}")


def init_logger(verbose: bool) -> None:
    """Setup the logger for this project

    Args:
        verbose (bool): Whether verbose logging in enabled
    """

    LOG.setLevel(logging.DEBUG)

    logPath = os.path.join(locations.ROOT, "logs")
    logName = time.strftime("%Y-%m-%d %H-%M", time.localtime())

    for i in os.listdir(logPath):
        os.remove(os.path.join(logPath, i))

    file_logger = logging.FileHandler(os.path.join(logPath, f"{logName}.log"))
    file_logger.setLevel(logging.DEBUG)
    file_logger.setFormatter(_log_formatter)
    LOG.addHandler(file_logger)

    console_logger = logging.StreamHandler(sys.stdout)
    console_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_logger.setFormatter(_log_formatter)
    LOG.addHandler(console_logger)


def append_http_logger(backend_ip: str, port: int, device: "FrontendDevice") -> None:
    """Starts the sending of important logging messages to the backend logging adapter

    Args:
        backend_ip (str): The IP received from the SSDP search
        port (int): The port of the backend WebServer
        device (FrontendDevice): The frontend device used for authentification
    """

    http_logger = HttpLogger(backend_ip, port, device)
    http_logger.setLevel(logging.WARNING)
    http_logger.setFormatter(_log_formatter)
    LOG.addHandler(http_logger)
