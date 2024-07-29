import logging
from socket import socket
import traceback
from device.api import FUNCS
import config
from utils import dumpb
from webserver.webrequest import WebRequest, WebResponse

LOG = logging.getLogger()


class FrontendRequest(WebRequest):
    def __init__(self, parent, conn: socket, addr: tuple[str, int]) -> None:
        super().__init__(parent, conn, addr)
        self.backend_ip = config.load_var("backend.ip")

    def REQUEST(self, path: str, body: dict) -> WebResponse:
        if self._addr[0] != self.backend_ip:
            return WebResponse(301, "MOVED", [("Location", f"{self.backend_ip}")])

        funcs = path.split("/")
        response = {}

        for f in funcs:
            try:
                fargs = f.split(".")

                for name, fclass in FUNCS.items():
                    if name.lower() == fargs[0].lower():
                        res = fclass(self, fargs[1:], body).api()

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

    def send_page(self, fname: str) -> None:
        return None

    def has_public(self) -> str:
        return None
