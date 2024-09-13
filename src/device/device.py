import base64
import gzip
import logging
from typing import Any
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

from hashlib import md5
import random

import requests

import config
from utils import CaseInsensitiveDict, CleanUp, dumpb, get_os_name
from webserver.webrequest import WebResponse


LOG = logging.getLogger(__name__)

KEY_SIZE = 2048
DEV_PORT = 4001


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

    def load_pub_key(self, key: str):
        """Loads the public key of the opponent

        Args:
            key (str): Key in a PEM string format
        """

        decomp = Device.decompress(key)
        pkey = serialization.load_pem_public_key(decomp)
        if isinstance(pkey, rsa.RSAPublicKey):
            self._pub_key = pkey

    def get_enc_token(self) -> str:
        """
        Returns:
            str: Token for the device in an key-encoded format
        """

        if self._pub_key == None:
            return ""

        return Device.compress(
            self._pub_key.encrypt(
                self._token.hex().encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        )

    def login(self, body: dict[str, Any]) -> WebResponse:
        """Try to login the current device from a post-body provided in the login API call

        Args:
            body (dict[str, Any]): The JSON body as a dict

        Returns:
            WebResponse: The response to forward to the opponent
        """

        try:
            if "key" not in body:
                LOG.debug("Key not in body")
            self.load_pub_key(body["key"])
            if "subdevices" not in body:
                LOG.debug("SubDevices not in body")
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
                        "token": self.get_enc_token(),
                    }
                ),
            )
        except:
            return WebResponse(
                400,
                "BAD_BODY",
                body=dumpb({"message": "Body has bad content"}),
            )

    def check_token(self, hdr: str) -> bool:
        """Checks if the provided token is valid for this device

        Args:
            hdr (str): The value of the `Authorization` header

        Returns:
            bool: Whether the token is valid
        """

        tk = hdr.replace("BEARER", "").strip()
        if tk.lower() == self._token.lower():
            return True

        for k in self._subdevices:
            if tk.lower() == k.token.lower():
                return True
        return False

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
            tuple[tuple[int, str], dict[str, str], tuple[bytes, str]]: The response from the frontend device
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

        r = requests.post(
            f"http://{self._ip}:{DEV_PORT}/{".".join(fargs)}",
            data=dumpb(body)[0],
            headers={"Content-Type": "application/json", "User-Agent": "JoaNetAPI"},
        )

        return WebResponse(
            r.status_code,
            r.reason,
            dict(r.headers),
            (r.content, r.headers.get("Content-Type", "application/octet-stream")),
        )

    def close(self) -> None:
        """Sends a close request to the frontend device"""

        try:
            requests.get(
                f"http://{self._ip}:{DEV_PORT}/close",
                headers={"User-Agent": "JoaNetAPI"},
            ).close()
        except Exception:
            LOG.exception("Failed close request for %s", self._ip)

    def logout(self) -> None:
        """Method called upon recieving of a logout request

        Note:
            Method awaits implementation [TODO]
        """

        pass


class FrontendDevice(CleanUp):
    def __init__(self) -> None:
        self._priv_key: rsa.RSAPrivateKey = rsa.generate_private_key(
            public_exponent=65537, key_size=KEY_SIZE
        )
        self._pub_key: rsa.RSAPublicKey = self._priv_key.public_key()
        self._token: str | None = None
        self._ip: str = str(config.load_var("backend"))

    def login(self, version: float) -> None:
        """Sends a login request to the backend device

        Args:
            version (float): The version of this device

        Raises:
            Exception: Upon a login failure
        """
        from frontend.frontend import FFUNCS

        pem: bytes = self._pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.PKCS1,
        )
        funcs = [k for k in FFUNCS.keys()]
        LOG.debug(f"Sending funcs: {funcs}")

        r = requests.post(
            f"http://{self._ip}:{DEV_PORT}/login",
            headers={"Content-Type": "application/json"},
            data=dumpb(
                {
                    "key": Device.compress(pem),
                    "funcs": funcs,
                    "subdevices": config.load_var("subdevices"),
                    "version": version,
                    "os": get_os_name(),
                }
            )[0],
        )

        if not r.ok:
            raise Exception("Login failed!")

        b = r.json()
        tok = Device.decompress(b["token"])
        self._token = self._priv_key.decrypt(
            tok,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        ).decode()

    def authorize(self) -> dict[str, str]:
        """
        Returns:
            dict[str, str]: A header dict including the `Authorization` header needed for this device
        """

        return {"Authorization": f"BEARER {self._token}"}

    def cleanup(self) -> None:
        r = requests.get(
            f"http://{self._ip}:{DEV_PORT}/logout",
            headers=self.authorize(),
        )
        if not r.ok:
            LOG.warning("Logout did not succeed!")
