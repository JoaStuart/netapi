import base64
import gzip
from io import BytesIO
import json
import logging
import traceback
from typing import Any, NoReturn
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

from hashlib import md5
import random

import requests

import config
from locations import VERSION
import locations
from utils import CaseInsensitiveDict, CleanUp, dumpb, get_os_name
from webclient.client_request import WebClient, WebMethod
from webserver.webrequest import WebResponse

from typing import TYPE_CHECKING


from log import LOG

KEY_SIZE = 2048
DEV_PORT = 4001

# Import PermissionLevel upon Type checking to avoid circular import
if TYPE_CHECKING:
    from device.permissions import PermissionLevel


class SubDevice:
    def __init__(self, name: str, token: str) -> None:
        self.name = name
        self.token = token


class Device:
    @staticmethod
    def make_device_token() -> bytes:
        """Generates a random device token

        Returns:
            bytes: The device token in bytes
        """

        return md5(random.randbytes(10)).digest()

    @staticmethod
    def compress(data: bytes) -> str:
        """Compresses a bytebuffer

        Args:
            data (bytes): The data to compress

        Returns:
            str: The compressed data as a string
        """

        return base64.standard_b64encode(gzip.compress(data)).decode()

    @staticmethod
    def decompress(data: str) -> bytes:
        """Decompresses the compressed string

        Args:
            data (str): The compressed data

        Returns:
            bytes: The original bytebuffer
        """

        return gzip.decompress(base64.standard_b64decode(data))

    def __init__(self, ip: str, container: dict[str, "Device"]) -> None:
        self._container = container
        self._ip: str = ip
        self._local_funcs: list[str] = ["logout"]
        self._token: bytes = Device.make_device_token()
        self._pub_key: rsa.RSAPublicKey | None = None
        self._subdevices: list[SubDevice] = []
        self._os: str = ""
        self._version: float = 0.0

        container[ip] = self

    def append_local_fun(self, name: str) -> None:
        """Add a new local function to the local function stack

        Args:
            name (str): Name of the function
        """

        LOG.debug(f"Local function {name} added for {self._ip}")
        if name.lower() not in self._local_funcs:
            self._local_funcs.append(name.lower())

    def has_local_fun(self, name: str) -> bool:
        """Checks if the provided function is on the local function stack

        Args:
            name (str): Name of the function

        Returns:
            bool: Whether the function is added to the stack or not
        """

        return name.lower() in self._local_funcs

    def compare_token(self, hextoken: str) -> bool:
        """Check the provided token

        Args:
            hextoken (str): The token in a hex format

        Returns:
            bool: Whether the token is valid
        """

        return bytes.fromhex(hextoken.strip()) == self._token

    def login(self, body: dict[str, Any]) -> WebResponse:
        """Try to login the current device from a post-body provided in the login API call

        Args:
            body (dict[str, Any]): The JSON body as a dict

        Returns:
            WebResponse: The response to forward to the opponent
        """

        if "subdevices" not in body:
            LOG.warning("SubDevices not in body")
            raise ValueError("Client must send Subdevices")

        self.load_subdevs(body["subdevices"])
        for k in body.get("funcs", []):
            self.append_local_fun(k)

        self._version = body.get("version", 0.0)
        self._os = body.get("os", "Unknown")

        return WebResponse(
            200,
            "LOGGED_IN",
            body=dumpb(
                {
                    "message": "Device logged in",
                    "token": self._token.hex(),
                    "update": VERSION > body.get("version", 0),
                }
            ),
        )

    def check_token(self, hdr: str) -> "PermissionLevel | None":
        """Checks if the provided token is valid for this device

        Args:
            hdr (str): The value of the `Authorization` header

        Returns:
            PermissionLevel | None: The permission level this token grants this device, or `None` if token is invalid
        """

        from device.permissions import (
            MaxPermissions,
            SubdevPermissions,
        )

        tk = hdr.lower().replace("bearer", "").strip()
        if tk == self._token.hex().lower():
            return MaxPermissions(self)

        for k in self._subdevices:
            if tk.lower() == k.token.lower():
                return SubdevPermissions(self)
        return None

    def load_subdevs(self, subdevs) -> None:
        """Load the subdevice from a JSON dict

        Args:
            subdevs (_type_): The JSON dict provided by the request
        """

        LOG.debug("Subdevices loading: %s", str(subdevs))
        for k in subdevs:
            self._subdevices.append(SubDevice(k["name"], k["token"]))

    def call_local_fun(
        self,
        fargs: list[str],
        body: dict[str, Any],
        recv_headers: CaseInsensitiveDict[str],
    ) -> WebResponse:
        """Call the provided function on the frontend device

        Args:
            fargs (list[str]): The arguments and function call to send
            body (dict[str, Any]): The body to send
            recv_headers (CaseInsensitiveDict[str]): The headers sent from the requesting device

        Returns:
            WebResponse: The response from the frontend device
        """

        if not self.has_local_fun(fargs[0]):
            raise NameError(
                f"The function provided could not be found: {".".join(fargs)}"
            )

        if fargs[0] == "logout":
            self.logout()
            return WebResponse(
                200, "LOGOUT", body=dumpb({"message": "Logout successful!"})
            )

        resp = (
            WebClient(self._ip, DEV_PORT)
            .set_method(WebMethod.POST)
            .set_path(f"/{".".join(fargs)}")
            .set_secure(True)
            .set_json(body)
            .send()
        )

        return WebResponse(
            resp.code,
            resp.msg,
            resp.headers,
            (resp.body, resp.get_header("Content-Type") or "application/octet-stream"),
        )

    def close(self) -> None:
        """Sends a close request to the frontend device"""

        WebClient(self._ip, DEV_PORT).set_path("/close").set_secure(True).set_timeout(
            0.1
        ).send()

    def logout(self) -> None:
        """Method called upon recieving of a logout request

        Note:
            Method awaits implementation [TODO]
        """

        pass


class FrontendDevice(CleanUp):
    def __init__(self, ip: str) -> None:
        self._token: str | None = None
        self._ip: str = ip

    def login(self, version: float) -> None | NoReturn:
        """Sends a login request to the backend device

        Args:
            version (float): The version of this device

        Raises:
            Exception: Upon a login failure
        """
        from frontend.frontend import FFUNCS

        funcs = [k for k in FFUNCS.keys()]
        LOG.debug(f"Sending funcs: {funcs}")

        resp = (
            WebClient(self._ip, DEV_PORT)
            .set_method(WebMethod.POST)
            .set_path("/login")
            .set_secure(True)
            .set_json(
                {
                    "funcs": funcs,
                    "subdevices": config.load_var("subdevices"),
                    "version": version,
                    "os": get_os_name(),
                }
            )
            .send()
        )

        if resp.code != 200:
            raise Exception("Login failed!")

        b = json.loads(resp.body)

        if b.get("update", False):
            self._update()

    def _update(self) -> None | NoReturn:
        """Downloads the latest packed sources and updates"""

        LOG.info("Starting update")
        dl = WebClient(self._ip, DEV_PORT).set_path("/pack.zip").send()

        if dl.code != 200:
            LOG.warning(
                f"Update failed because of content download response {dl.code}: {dl.msg}"
            )
            return

        zbinary = BytesIO(dl.body)
        locations.unpack(zbinary)

        LOG.info("Finished update, restarting...")
        from main import restart

        restart()

    def _action_client(self, actions: str) -> WebClient:
        """Generates a WebClient to perform these actions

        Returns:
            WebClient: The WebClient with all configurations set
        """

        return (
            WebClient(self._ip, DEV_PORT)
            .set_path(actions)
            .set_secure(True)
            .authorize(self._token)
        )

    def cleanup(self) -> None:
        resp = self._action_client("/logout").send()
        if resp.code != 200:
            LOG.warning("Logout did not succeed!")
