import logging
import traceback
from typing import Any, Type
import urllib.parse
from backend.output import OUTPUTS, OutputDevice
from backend.sensor import SENSORS
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
                if self._addr[0] not in DEVICES:
                    if fargs[0] == "login":
                        try:
                            dev = Device(self._addr[0])
                            dev.load_pub_key(body["key"])
                            for k in body.get("funcs", []):
                                dev.append_local_fun(k)
                            DEVICES[self._addr[0]] = dev

                            return WebResponse(
                                200,
                                "LOGGED_IN",
                                body=dumpb(
                                    {
                                        "message": "Device logged in",
                                        "token": dev.get_enc_token(),
                                    }
                                ),
                            )
                        except:
                            return WebResponse(
                                400,
                                "BAD_BODY",
                                body=dumpb({"message": "Body has bad content"}),
                            )
                    return WebResponse(
                        401,
                        "NOT_LOGIN",
                        body=dumpb(
                            {
                                "message": "You need to first log in the device by starting the frontend."
                            }
                        ),
                    )
                device = DEVICES[self._addr[0]]

                # Change output device
                if fargs[0].startswith(":"):
                    for name, oclass in OUTPUTS.items():
                        if name.lower() == fargs[0].lower().lstrip(":"):
                            outputtype = oclass
                            continue

                # Check sensor data
                for name, sclass in SENSORS.items():
                    if name.lower() == fargs[0]:
                        inst = sclass()
                        inst.tpoll()
                        out = outputtype(body)
                        inst.to(out)
                        if type(response) == dict:
                            response |= out.api_resp()
                            headers |= out.api_headers()
                            code = out.api_response(code)
                        continue

                # Execute backend function and display response
                for name, fclass in BFUNC.items():
                    if name.lower() == fargs[0].lower():
                        res = fclass(self, fargs[1:], body).api()

                        if isinstance(response, dict):
                            if isinstance(res, dict):
                                response |= res
                            else:
                                response = res

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
