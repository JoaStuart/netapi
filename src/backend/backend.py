import json
import logging
from socket import socket
import traceback
import urllib.parse
from typing import Any, Type

from device import api
from device.permissions import DefaultPermissions, PermissionLevel
from utils import dumpb
from device.api import APIFunct
from device.device import Device
from backend.sensor import SENSORS
from locations import PL_BFUNC
from backend.output import OUTPUTS, OutputDevice
from webserver.webrequest import WebRequest, WebResponse


LOG = logging.getLogger()


BFUNC: dict[str, Type[APIFunct]] = api.load_dir(PL_BFUNC)

DEVICES: dict[str, Device] = {}


class FinishError(RuntimeError):
    def __init__(self, response: WebResponse) -> None:
        super().__init__()

        self._response = response

    def get_response(self) -> WebResponse:
        return self._response


class BackendRequest(WebRequest):
    def __init__(
        self, parent, conn: socket, addr: tuple[str, int], args: dict[str, Any]
    ) -> None:
        super().__init__(parent, conn, addr, args)

        self.outputtype: Type[OutputDevice] = OUTPUTS["default"]
        self.response: dict[str, str] | tuple[bytes, str] = {}
        self.headers: dict[str, str] = {}
        self.code: tuple[int, str] = (200, "OK")

        self.perms: PermissionLevel = DefaultPermissions()

    def REQUEST(self, pth: str, body: dict) -> WebResponse:
        """Method that gets executed upon a request

        Args:
            pth (str): Path requested
            body (dict): JSON body of the request or {} if no or non-JSON body

        Returns:
            WebResponse: The response to be sent back

        Notes:
            Method awaits refactoring [TODO]
        """

        path: str = urllib.parse.unquote(pth)

        for k in path.split("/")[1:]:
            if len(k) == 0:
                continue
            fargs = k.split(".")

            try:
                if r := self._handle(fargs, body):
                    return r

            except FinishError as e:
                return e.get_response()

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
            *self.code,
            headers=self.headers,
            body=(
                dumpb(self.response)
                if isinstance(self.response, dict)
                else self.response
            ),
        )

    def _login(self, body: dict):
        """Performs a login using the arguments given in the body

        Args:
            body (dict): Body with arguments from device logging in

        Raises:
            FinishError: Immediate response
        """

        dev = Device(self._addr[0], DEVICES)
        raise FinishError(dev.login(body))

    def _get_device(self) -> None:
        """Gets the device and permission level of this connection

        Raises:
            FinishError: Immediate return upon invalid token
        """

        device = DEVICES.get(self._addr[0], None)
        if device is None:
            return

        token = self._recv_headers.get("Authorization")
        if token is None:
            return

        perms = device.check_token(token)
        if perms is None:
            raise FinishError(
                WebResponse(
                    status_code=401,
                    status_msg="INVALID_TOK",
                    body=dumpb({"message": "The provided token is invalid!"}),
                )
            )

        self.perms = perms

    def _check_permissions(self, expected: int, fargs: list[str]) -> None:
        if self.perms.int_level() >= expected:
            return

        raise FinishError(
            WebResponse(
                status_code=403,
                status_msg="NO_PERMS",
                body=dumpb(
                    {
                        "message": f"Not enough permissions to execute `{".".join(fargs)}`!"
                    }
                ),
            )
        )

    def _change_output_device(self, fargs: list[str]) -> bool:
        """Tries to change the output device to the requested device

        Args:
            fargs (list[str]): Arguments of the current command

        Returns:
            bool: Whether the command was successful
        """

        if fargs[0].startswith(":"):
            for name, oclass in OUTPUTS.items():
                if name.lower() == fargs[0].lower().lstrip(":"):
                    self.outputtype = oclass
                    return True

        return False

    def _check_sensor_data(self, fargs: list[str], body: dict) -> bool:
        """Tries to read the sensor data of the requested sensor

        Args:
            fargs (list[str]): Arguments of the current command
            body (dict): Body of current connection

        Returns:
            bool: Whether the command was successful
        """

        for name, inst in SENSORS.items():
            if name.lower() == fargs[0].lower():
                inst.tpoll()
                if inst.data is None:
                    continue

                out = self.outputtype(body)
                inst.to(out, fargs[1:])
                if type(self.response) == dict:
                    self.response |= out.api_resp()
                    self.headers |= out.api_headers()
                    self.code = out.api_response(self.code)

                return True

        return False

    def _execute_backend(self, fargs: list[str], body: dict) -> bool:
        """Tries to execute the requested backend function

        Args:
            fargs (list[str]): Arguments of the current command
            body (dict): Body of current connection

        Returns:
            bool: Whether the command was successful
        """

        for name, fclass in BFUNC.items():
            if name.lower() == fargs[0].lower():
                self._check_permissions(50, fargs)

                res = fclass(self, fargs[1:], body).api()

                if isinstance(self.response, dict):
                    if isinstance(res, dict):
                        self.response |= res
                    else:
                        self.response = res

                return True

        return False

    def _execute_frontend(self, device: Device, fargs: list[str], body: dict) -> bool:
        """Tries to execute the frontend function on the connecting device

        Args:
            device (Device): The device to execute the function on
            fargs (list[str]): Arguments of the current command
            body (dict): Body of current connection

        Returns:
            bool: Whether the command was successful
        """

        if device.has_local_fun(fargs[0]):
            self._check_permissions(50, fargs)

            resp = device.call_local_fun(fargs, body, self._recv_headers)
            self.code = (resp.code, resp.msg)
            self.headers |= resp.headers
            if isinstance(self.response, dict):
                data, tpe = resp.body
                if tpe.lower() == "application/json":
                    jdta = json.loads(data)
                    self.response |= jdta
                else:
                    self.response = (data, tpe)
            return True

        return False

    def _handle(self, fargs: list[str], body: dict):
        # Try to log device in
        if fargs[0] == "login":
            self._login(body)

        # Get the current device and permission level
        self._get_device()

        # Change output device
        if self._change_output_device(fargs):
            return

        # Check sensor data
        if self._check_sensor_data(fargs, body):
            return

        # Execute backend function
        if self._execute_backend(fargs, body):
            return

        # Execute frontend function
        if (device := self.perms.device()) is not None:
            if self._execute_frontend(device, fargs, body):
                return

        raise FinishError(
            WebResponse(
                404,
                "FUNC_NOT_FOUND",
                body=dumpb({"message": f"API function `{".".join(fargs)}` not found!"}),
            )
        )
