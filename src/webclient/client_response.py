import socket
from typing import Any, TypeVar

from encryption.enc_socket import EncryptedSocket
from utils import CaseInsensitiveDict


class ClientResponse:
    def __init__(self, sock: EncryptedSocket, keep_alive: bool = False) -> None:
        self._sock = sock
        self._keep_alive = keep_alive

        self._read_status()
        self._read_headers()
        self._read_body()

    def _read_line(self) -> str:
        """Reads one line of the incoming data

        Returns:
            str: The line read
        """

        buffer = []

        # Read one byte at a time into `buffer` until \n is encountered
        while (r := self._sock.recv(1)) != b"\n":
            buffer.append(r)

        # Append \n because the loop exited without writing it
        buffer.append(b"\n")

        return b"".join(buffer).decode()

    def _read_status(self) -> None:
        """Reads the status line and parses it"""

        _, code, self._msg = self._read_line().split(" ", 2)
        self._code = int(code)

    def _read_headers(self) -> None:
        """Reads all headers the server sent"""

        self._headers: CaseInsensitiveDict[str] = CaseInsensitiveDict({})

        # Read header until empty line is encountered
        while len(l := self._read_line().strip()) > 0:
            k, v = l.split(": ", 1)
            self._headers[k] = v

    def _read_body(self) -> None:
        """Reads the body if sent and closes socket depending on `self._close_after`"""

        # Checks if data should be received
        self._data = b""
        if not ("Content-Type" in self._headers and "Content-Length" in self._headers):
            return

        # Reads data from socket
        con_len = int(self._headers["Content-Length"])
        self._data = self._sock.recv(con_len)

        # Closes socket if not keeping alive
        if not self._keep_alive:
            self._sock.close()

    def get_header(self, key: str, default: str | None = None) -> str | None:
        """Gets the header of the response by key or returns a default value if not existent

        Args:
            key (str): The key of the header to read
            default (str | None, optional): The default value that returns when the header was not sent. Defaults to None.

        Returns:
            str | None: The value of the header or `default`
        """

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
