import socket
from typing import Any, TypeVar

from encryption.enc_socket import EncryptedSocket
from utils import CaseInsensitiveDict


class ClientResponse:
    def __init__(self, sock: EncryptedSocket, close_after: bool = True) -> None:
        self._sock = sock
        self._close_after = close_after

        self._read_status()
        self._read_headers()
        self._read_body()

    def _read_line(self) -> str:
        buffer = []

        while (r := self._sock.recv(1)) != b"\n":
            buffer.append(r)

        buffer.append(b"\n")

        return b"".join(buffer).decode()

    def _read_status(self) -> None:
        _, code, self._msg = self._read_line().split(" ", 2)
        self._code = int(code)

    def _read_headers(self) -> None:
        self._headers: CaseInsensitiveDict[str] = CaseInsensitiveDict({})

        while len(l := self._read_line().strip()) > 0:
            k, v = l.split(": ", 1)
            self._headers[k] = v

    def _read_body(self) -> None:
        self._data = b""
        if not ("Content-Type" in self._headers and "Content-Length" in self._headers):
            return

        con_len = int(self._headers["Content-Length"])
        self._data = self._sock.recv(con_len)

        if self._close_after:
            self._sock.close()

    def get_header(self, key: str, default: str | None = None) -> str | None:
        return self._headers.get(key, default)

    @property
    def code(self) -> int:
        return self._code

    @property
    def msg(self) -> str:
        return self._msg

    @property
    def headers(self) -> dict[str, str]:
        return self._headers.dict()

    @property
    def body(self) -> bytes:
        return self._data
