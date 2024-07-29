import json
import logging
import traceback
from typing import Any, Type
import urllib.parse
from backend.output import OUTPUTS, OutputDevice
from backend.sensor import SENSORS
from device.api import FUNCS
from utils import dumpb
from webserver.webrequest import WebRequest, WebResponse


LOG = logging.getLogger()


class BackendRequest(WebRequest):
    def REQUEST(self, path: str, body: dict) -> WebResponse:
        path: str = urllib.parse.unquote(path)

        outputtype: Type[OutputDevice] = OUTPUTS["default"]
        response: dict[str, Any] = {}
        headers: dict[str, str] = {}
        for k in path.split("/")[1:]:
            if len(k) == 0:
                continue
            fargs = k.split(".")
            try:

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
                        out = outputtype()
                        inst.to(out)
                        if type(response) == dict:
                            response |= out.api_resp()
                            headers |= out.api_headers()
                        continue

                # Execute backend function and display response
                for name, fclass in FUNCS.items():
                    if name.lower() == fargs[0].lower():
                        res = fclass(self, fargs[1:], body).api()

                        if type(res) == dict:
                            response |= res
                        else:
                            response = res

                # TODO send API function to frontend

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
            200,
            "OK",
            headers=headers,
            body=dumpb(response) if type(response) == dict else response,
        )
