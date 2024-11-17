from enum import Enum
import json
import logging
import socket
from typing import Any

from encryption.dh_key_ex import DHClient, DHServer
from encryption.enc_socket import EncryptedSocket
from encryption.encryption import AesEncryption
import locations
from webclient.client_response import ClientResponse

LOG = logging.getLogger()


class WebMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    SECURE = "SECURE"


class WebClient:
    VERSION = "HTTP/1.1"

    @staticmethod
    def url(url: str) -> "WebClient":
        if "://" in url:
            proto, url = url.split("://", 1)

            if proto != "http":
                raise ValueError("This WebClient only implements http:// requests!")

        if "/" in url:
            url, path = url.split("/", 1)
        else:
            path = ""

        if ":" in url:
            url, port = url.split(":", 1)
        else:
            port = "80"

        return WebClient(url, int(port)).set_path(path)

    def __init__(self, ip: str, port: int) -> None:
        self._ip = ip
        self._port = port
        self._method = WebMethod.GET
        self._path = "/"
        self._headers: dict[str, Any] = self._default_headers()
        self._json: dict[str, Any] = {}
        self._data: tuple[bytes, str] | None = None
        self._secure: bool = False

    def set_secure(self, secure: bool) -> "WebClient":
        self._secure = secure
        return self

    def add_header(self, key: str, val: str) -> "WebClient":
        self._headers[key] = val
        return self

    def has_header(self, key: str) -> bool:
        return key in self._headers

    def del_header(self, key: str) -> "WebClient":
        del self._headers[key]
        return self

    def set_json(self, body: dict[str, Any]) -> "WebClient":
        self._json = body
        return self

    def set_data(self, data: bytes, mime: str) -> "WebClient":
        self._data = (data, mime)
        return self

    def set_method(self, method: WebMethod) -> "WebClient":
        self._method = method
        return self

    def get_method(self) -> WebMethod:
        return self._method

    def set_path(self, path: str) -> "WebClient":
        self._path = path
        return self

    def get_path(self) -> str:
        return self._path

    def set_timeout(self, timeout: float) -> "WebClient":
        socket.setdefaulttimeout(timeout)
        return self

    def authorize(self, token: str | None) -> "WebClient":
        if token is not None:
            self.add_header("Authorization", f"BEARER {token}")
        return self

    def _send_status(self, sock: EncryptedSocket) -> None:
        sock.send(f"{self._method.value} {self._path} {WebClient.VERSION}\r\n".encode())

    def _send_headers(self, sock: EncryptedSocket) -> None:
        for k, v in self._headers.items():
            sock.send(f"{k}: {str(v)}\r\n".encode())

    def _send_secure(self, sock: EncryptedSocket) -> None:
        dh = DHClient()

        sock.send(
            "\r\n".join(
                [
                    f"{WebMethod.SECURE.value} * {WebClient.VERSION}",
                    f"DH-E: {str(dh.get_e())}",
                    "\r\n",
                ]
            ).encode()
        )
        sock.flush()

        secure_resp = ClientResponse(sock, False)
        dh.read_f(int(str(secure_resp.get_header("DH-F"))))
        LOG.debug("Finished SECURE handshake with %s, changing encryption", self._ip)

        sock.update_encryption(
            AesEncryption(
                dh.make_enc_key(AesEncryption.key_len()),
                dh.make_iv_str(AesEncryption.iv_len()),
            )
        )

    def _send_request(self, sock: EncryptedSocket) -> None:
        has_body = self._method == WebMethod.POST or self._method == WebMethod.PUT
        if has_body:
            if self._data is None:
                self._data = (json.dumps(self._json).encode(), "application/json")

            self._headers["Content-Type"] = self._data[1]
            self._headers["Content-Length"] = len(self._data[0])

        self._send_status(sock)
        self._send_headers(sock)
        sock.send(b"\r\n")

        if has_body:
            # Ignore warning for self._data maybe being None,
            # because it gets set in the IF statement above
            sock.send(self._data[0])  # type: ignore
        sock.flush()

    def send(self) -> ClientResponse:
        LOG.debug(
            "Sending request of %s %s to %s:%d",
            self._method.value,
            self._path,
            self._ip,
            self._port,
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect((self._ip, self._port))
        enc_sock = EncryptedSocket(sock)

        if self._secure:
            self._send_secure(enc_sock)

        self._send_request(enc_sock)

        return ClientResponse(enc_sock)

    def _default_headers(self) -> dict[str, str]:
        return {
            "Accept": "*/*",
            # TODO maybe Accept-Encoding
            "Cache-Control": "no-cache",
            "User-Agent": f"JoaNetAPI/{locations.VERSION}",
        }
