import base64
import gzip
from typing import Any
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

from hashlib import md5
import random

import requests

from utils import CaseInsensitiveDict, dumpb


class Device:
    KEY_SIZE = 2048
    DEV_PORT = 4001

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

    def append_local_fun(self, name: str) -> None:
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

    def call_local_fun(
        self,
        fargs: list[str],
        body: dict[str, Any],
        recv_headers: CaseInsensitiveDict[str],
    ) -> tuple[tuple[int, str], dict[str, str], tuple[bytes, str]]:
        r = requests.post(
            f"http://{self._ip}:{Device.DEV_PORT}/{".".join(fargs)}",
            data=dumpb(body)[0],
            headers=recv_headers.dict() | {"content-type": "application/json"},
        )

        return (
            (r.status_code, r.reason),
            dict(r.headers),
            (r.content, r.headers.get("Content-Type", "application/octet-stream")),
        )
