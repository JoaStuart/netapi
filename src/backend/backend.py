import logging
import traceback
from typing import Any, Type
import urllib.parse
from backend.output import OUTPUTS, OutputDevice
from backend.sensor import SENSORS
import config
from device.device import Device
from device import api
from device.api import APIFunct
from locations import PL_BFUNC, PL_FFUNC
from utils import dumpb
from webserver.webrequest import WebRequest, WebResponse


LOG = logging.getLogger()


BFUNC: dict[str, Type[APIFunct]] = api.load_dir(PL_BFUNC)
FFUNC: dict[str, Type[APIFunct]] = api.load_dir(PL_FFUNC)

DEVICES: dict[str, Device] = {}


class BackendRequest(WebRequest):
    def REQUEST(self, pth: str, body: dict) -> WebResponse:
        path: str = urllib.parse.unquote(pth)

        outputtype: Type[OutputDevice] = OUTPUTS["default"]
        response: dict[str, Any] | tuple[bytes, str] = {}
        headers: dict[str, str] = {}
        code: tuple[int, str] = (200, "OK")
        for k in path.split("/")[1:]:
            if len(k) == 0:
                continue
            fargs = k.split(".")
            try:
                # Try to log device in
                if self._addr[0] not in DEVICES or fargs[0] == "login":
                    DEVICES[self._addr[0]] = dev = Device(self._addr[0])
                    if fargs[0] == "login":
                        return dev.login(body)
                    else:
                        del DEVICES[self._addr[0]]

                    return WebResponse(
                        401,
                        "NOT_LOGIN",
                        body=dumpb(
                            {
                                "message": "You need to first log in the device by starting the frontend."
                            }
                        ),
                    )
                else:
                    device = DEVICES[self._addr[0]]
                    if (
                        not device.check_token(
                            self._recv_headers.get("Authorization") or ""
                        )
                        and self._addr[0] != "127.0.0.1"
                    ):
                        return WebResponse(
                            401,
                            "INVALID_TOK",
                            body=dumpb(
                                {
                                    "message": (
                                        "The token provided is not valid"
                                        if "Authorization" in self._recv_headers
                                        else "No token provided"
                                    )
                                }
                            ),
                        )

                # Change output device
                out = False
                if fargs[0].startswith(":"):
                    for name, oclass in OUTPUTS.items():
                        if name.lower() == fargs[0].lower().lstrip(":"):
                            outputtype = oclass
                            out = True
                            break
                if out:
                    continue

                # Check sensor data
                sensor = False
                for name, sclass in SENSORS.items():
                    if name.lower() == fargs[0].lower():
                        LOG.debug("%s sensor chosen", name)
                        inst = sclass(fargs[1:])
                        inst.tpoll()
                        out = outputtype(body)
                        inst.to(out)
                        if type(response) == dict:
                            response |= out.api_resp()
                            headers |= out.api_headers()
                            code = out.api_response(code)

                        sensor = True
                        break
                if sensor:
                    continue

                # Execute backend function and display response
                bfunc = False
                for name, fclass in BFUNC.items():
                    if name.lower() == fargs[0].lower():
                        res = fclass(self, fargs[1:], body).api()

                        if isinstance(response, dict):
                            if isinstance(res, dict):
                                response |= res
                            else:
                                response = res

                        bfunc = True
                        break
                if bfunc:
                    continue

                if device.has_local_fun(fargs[0]):
                    r_code, r_hdrs, r_resp = device.call_local_fun(
                        fargs, body, self._recv_headers
                    )
                    code = r_code
                    headers |= r_hdrs
                    if isinstance(response, dict):
                        if isinstance(r_resp, dict):
                            response |= r_resp
                        else:
                            response = r_resp
                    continue

                return WebResponse(
                    404,
                    "FUNC_NOT_FOUND",
                    body=dumpb(
                        {"message": f"API function `{".".join(fargs)}` not found!"}
                    ),
                )

            except Exception:
                LOG.exception(f"Exception on {".".join(fargs)}")
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
