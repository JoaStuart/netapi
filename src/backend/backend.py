import json
import logging
from socket import socket
import traceback
import urllib.parse
from typing import Any, Type

from device import api
from device.permissions import DefaultPermissions, PermissionLevel
from utils import dumpb
from device.api import APIFunct, APIResult
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
        self.response: APIResult = APIResult.empty()
        self.headers: dict[str, str] = {}

        self.perms: PermissionLevel = DefaultPermissions()
        self.dev: Device | None = None

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

        return self.response.webresponse()

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
        self.device = device

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

                if isinstance(self.response.json, dict):
                    self.response.set_json = self.response.json or out.api_resp()
                self.headers |= out.api_headers()

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
                api = fclass(self, fargs[1:], body)
                self._check_permissions(api.permissions(50), fargs)

                self.response.combine(fargs[0], api.api())

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
            resp = device.call_local_fun(fargs, body, self._recv_headers, self.perms)
            self.headers |= resp.headers
            if isinstance(self.response, dict):
                data, tpe = resp.body
                if tpe.lower() == "application/json":
                    jdta = json.loads(data)
                    self.response.combine(
                        fargs[0], APIResult.by_json(jdta, success=resp.code == 200)
                    )
                else:
                    self.response.combine(
                        fargs[0], APIResult.by_data(data, tpe, success=resp.code == 200)
                    )
            return True

        return False

    def _handle(self, fargs: list[str], body: dict):
        # Try to log device in
        if fargs[0] == "login":
            self._login(body)

        # Get the current device and permission level
        self._get_device()

        # Try to log out
        if self.dev != None and fargs[0] == "logout":
            self.dev.logout()
            del DEVICES[self._addr[0]]
            raise FinishError(WebResponse(200, "LOGGED_OUT"))

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

    @staticmethod
    def execute_backend(fargs: list[str], body: dict) -> None:
        """Execute a backend function without needing a WebRequest

        Args:
            fargs (list[str]): Arguments of the current command
            body (dict): Body for the current command
        """

        for name, fclass in BFUNC.items():
            if name.lower() == fargs[0].lower():
                fclass(None, fargs[1:], body).api()

                LOG.info("Executed backend /%s", ".".join(fargs))
                return

        LOG.warning("Could not find BFunc for `%s`!" ".".join(fargs))
