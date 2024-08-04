import logging
from socket import socket
import traceback
from typing import Any, Type
import config
from device import api
from device.api import APIFunct
from locations import PL_FFUNC
from utils import dumpb
from webserver.webrequest import WebRequest, WebResponse

LOG = logging.getLogger()


FFUNCS: dict[str, Type[APIFunct]] = api.load_dir(PL_FFUNC)


class FrontendRequest(WebRequest):
    def __init__(self, parent, conn: socket, addr: tuple[str, int]) -> None:
        super().__init__(parent, conn, addr)
        self.backend_ip = config.load_var("backend")

    def REQUEST(self, path: str, body: dict) -> WebResponse:
        if self._addr[0] != self.backend_ip:
            LOG.debug(f"Redirecting to {self.backend_ip}")
            return WebResponse(
                301,
                "MOVED",
                {"Location": f"http://{self.backend_ip}:4001{path}"},
            )

        funcs = path.split("/")
        response: dict[str, Any] | tuple[bytes, str] = {}
        headers: dict[str, str] = {}
        code: tuple[int, str] = (200, "OK")

        for f in funcs:
            try:
                fargs = f.split(".")

                for name, fclass in FFUNCS.items():
                    if name.lower() == fargs[0].lower():
                        res = fclass(self, fargs[1:], body).api()

                        if type(response) == dict:
                            if type(res) == dict:
                                response |= res
                            else:
                                response = res
            except Exception:
                LOG.exception(f"Exception on function `{".".join(fargs)}`")
                return WebResponse(
                    500,
                    "FUNC_FAILED",
                    body=dumpb(
                        {
                            "message": f"Function `{".".join(fargs)}` failed!",
                            "exception": traceback.format_exc(),
                        }
                    ),
                )

        return WebResponse(
            *code,
            headers=headers,
            body=dumpb(response) if isinstance(response, dict) else response,
        )

    def send_page(self, fname: str) -> None:
        return None

    def has_public(self) -> str | None:
        return None
