import logging
import os
from socket import socket
import traceback
from typing import Any, Type
import config
from device import api
from device.api import APIFunct, APIResult
from locations import PL_FFUNC
from utils import dumpb
from webserver.webrequest import WebRequest, WebResponse

LOG = logging.getLogger()


FFUNCS: dict[str, Type[APIFunct]] = api.load_dir(PL_FFUNC)


class FrontendRequest(WebRequest):
    def __init__(
        self, parent, conn: socket, addr: tuple[str, int], args: dict[str, Any]
    ) -> None:
        super().__init__(parent, conn, addr, args)
        self.backend_ip = str(args["ip"])

    def REQUEST(self, path: str, body: dict) -> WebResponse:
        """Method called upon a request is recieved

        Args:
            path (str): The path of the request
            body (dict): The body sent, or {} if no body or non-JSON body is recieved

        Returns:
            WebResponse: The response to be sent back
        """

        if self._addr[0] != self.backend_ip:
            LOG.debug(f"Redirecting to {self.backend_ip}")
            return WebResponse(
                301,
                "MOVED",
                {"Location": f"http://{self.backend_ip}:4001{path}"},
            )

        funcs = path.split("/")
        response: APIResult = APIResult.empty()

        try:
            perms: int = int(self._recv_headers["Permissions"])
        except Exception:
            perms: int = 0

        for f in funcs:
            try:
                fargs = f.split(".")

                if fargs[0].lower() == "close":
                    LOG.info("Close request recieved")
                    self._parent._started = False
                    return WebResponse(
                        200, "CLOSED", body=dumpb({"message": "Closed!"})
                    )

                for name, fclass in FFUNCS.items():
                    if name.lower() == fargs[0].lower():
                        c = fclass(self, fargs[1:], body)
                        if perms > c.permissions(50):
                            return WebResponse(
                                status_code=403,
                                status_msg="NO_PERMS",
                                body=dumpb(
                                    {
                                        "message": f"Not enough permissions to execute `{".".join(fargs)}`!"
                                    }
                                ),
                            )

                        response.combine(fargs[0], c.api())
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

        return response.webresponse()

    def send_page(self, fname: str) -> None:
        """Disable public pages for frontend server"""

        return None

    def has_public(self) -> str | None:
        """Disable public pages for frontend server"""

        return None
