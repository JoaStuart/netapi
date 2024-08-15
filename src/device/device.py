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
from frontend.frontend import FFUNCS
from utils import CaseInsensitiveDict, CleanUp, dumpb
from webserver.webrequest import WebResponse


LOG = logging.getLogger()

KEY_SIZE = 2048
DEV_PORT = 4001


class SubDevice:
    def __init__(self, name: str, token: str) -> None:
        self.name = name
        self.token = token


class Device:
    @staticmethod
    def make_device_token() -> bytes:
        return md5(random.randbytes(10)).digest()

    @staticmethod
    def compress(data: bytes) -> str:
        return base64.standard_b64encode(gzip.compress(data)).decode()

    @staticmethod
    def decompress(data: str) -> bytes:
        return gzip.decompress(base64.standard_b64decode(data))

    def __init__(self, ip: str) -> None:
        self._ip = ip
        self._local_funcs: list[str] = []
        self._token: bytes = Device.make_device_token()
        self._pub_key: rsa.RSAPublicKey | None = None
        self._subdevices: list[SubDevice] = []

    def append_local_fun(self, name: str) -> None:
        LOG.debug(f"Local function {name} added for {self._ip}")
        if name.lower() not in self._local_funcs:
            self._local_funcs.append(name.lower())

    def has_local_fun(self, name: str) -> bool:
        return name.lower() in self._local_funcs

    def compare_token(self, hextoken: str) -> bool:
        return bytes.fromhex(hextoken.strip()) == self._token

    def load_pub_key(self, key: str):
        decomp = Device.decompress(key)
        pkey = serialization.load_pem_public_key(decomp)
        if isinstance(pkey, rsa.RSAPublicKey):
            self._pub_key = pkey

    def get_enc_token(self) -> str:
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
        try:
            if "key" not in body:
                LOG.debug("Key not in body")
            self.load_pub_key(body["key"])
            if "subdevices" not in body:
                LOG.debug("SubDevices not in body")
            self.load_subdevs(body["subdevices"])
            for k in body.get("funcs", []):
                self.append_local_fun(k)

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
        tk = hdr.replace("BEARER", "").strip()
        LOG.debug("%s: %s", hdr, tk)
        if tk.lower() == self._token.lower():
            return True

        for k in self._subdevices:
            if tk.lower() == k.token.lower():
                return True
        return False

    def load_subdevs(self, subdevs) -> None:
        LOG.debug("Subdevices loading: %s", str(subdevs))
        for k in subdevs:
            self._subdevices.append(SubDevice(k["name"], k["token"]))

    def call_local_fun(
        self,
        fargs: list[str],
        body: dict[str, Any],
        recv_headers: CaseInsensitiveDict[str],
    ) -> tuple[tuple[int, str], dict[str, str], tuple[bytes, str]]:
        r = requests.post(
            f"http://{self._ip}:{DEV_PORT}/{".".join(fargs)}",
            data=dumpb(body)[0],
            headers={"Content-Type": "application/json", "User-Agent": "JoaNetAPI"},
        )

        return (
            (r.status_code, r.reason),
            dict(r.headers),
            (r.content, r.headers.get("Content-Type", "application/octet-stream")),
        )

    def close(self) -> None:
        try:
            requests.get(
                f"http://{self._ip}:{DEV_PORT}/close",
                headers={"User-Agent": "JoaNetAPI"},
            ).close()
        except Exception:
            LOG.exception("Failed close request for %s", self._ip)


class FrontendDevice(CleanUp):
    def __init__(self) -> None:
        self._priv_key: rsa.RSAPrivateKey = rsa.generate_private_key(
            public_exponent=65537, key_size=KEY_SIZE
        )
        self._pub_key: rsa.RSAPublicKey = self._priv_key.public_key()
        self._token: str | None = None
        self._ip: str = str(config.load_var("backend"))

    def login(self) -> None:
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
        return {"Authorization": f"BEARER {self._token}"}

    def cleanup(self) -> None:
        pass  # TODO logout
