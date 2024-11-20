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

from log import LOG


class WebMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    SECURE = "SECURE"


class WebClient:
    VERSION = "HTTP/1.1"

    @staticmethod
    def url(url: str) -> "WebClient":
        """Creates a WebClient using the provided URL

        Args:
            url (str): The url to create the WebClient from

        Raises:
            ValueError: Error raised when using a protocol which is not `http`

        Returns:
            WebClient: The created client
        """

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
        """
        Args:
            secure (bool): Whether to use the `SECURE` protocol

        Returns:
            WebClient: Returns `self`, used for chaining
        """

        self._secure = secure
        return self

    def add_header(self, key: str, val: str) -> "WebClient":
        """
        Args:
            key (str): Key of the added header
            val (str): Value of the added header

        Returns:
            WebClient: Returns `self`, used for chaining
        """

        self._headers[key] = val
        return self

    def has_header(self, key: str) -> bool:
        """
        Args:
            key (str): Key of the header to check

        Returns:
            bool: Whether the header was set
        """

        return key in self._headers

    def del_header(self, key: str) -> "WebClient":
        """
        Args:
            key (str): Key of the header to remove

        Returns:
            WebClient: Returns `self`, used for chaining
        """

        del self._headers[key]
        return self

    def set_json(self, body: dict[str, Any]) -> "WebClient":
        """
        Args:
            body (dict[str, Any]): The JSON body to send

        Returns:
            WebClient: Returns `self`, used for chaining

        Notes:
            The method must be set to `POST` or `PUT` for this to be sent
        """

        self._json = body
        return self

    def set_data(self, data: bytes, mime: str) -> "WebClient":
        """
        Args:
            data (bytes): The raw data in bytes
            mime (str): The MIME type of this data

        Returns:
            WebClient: Returns `self`, used for chaining

        Notes:
            The method must be set to `POST` or `PUT` for this to be sent
        """

        self._data = (data, mime)
        return self

    def set_method(self, method: WebMethod) -> "WebClient":
        """
        Args:
            method (WebMethod): The method to be used in this request

        Returns:
            WebClient: Returns `self`, used for chaining
        """

        self._method = method
        return self

    def get_method(self) -> WebMethod:
        """
        Returns:
            WebMethod: The method used for this request
        """

        return self._method

    def set_path(self, path: str) -> "WebClient":
        """

        Args:
            path (str): The path to set for this request

        Returns:
            WebClient: Returns `self`, used for chaining
        """

        self._path = path
        return self

    def get_path(self) -> str:
        """
        Returns:
            str: The path used in this request
        """

        return self._path

    def set_timeout(self, timeout: float) -> "WebClient":
        """
        Args:
            timeout (float): The timeout set for socket operations

        Returns:
            WebClient: Returns `self`, used for chaining
        """

        socket.setdefaulttimeout(timeout)
        return self

    def authorize(self, token: str | None) -> "WebClient":
        """
        Args:
            token (str | None): The token to authorize this request with

        Returns:
            WebClient: Returns `self`, used for chaining

        Notes:
            The authorization is done using the `Authorization: BEARER <TOKEN>` header
        """

        if token is not None:
            self.add_header("Authorization", f"BEARER {token}")
        return self

    def _send_status(self, sock: EncryptedSocket) -> None:
        """Sends the status line

        Args:
            sock (EncryptedSocket): The socket to send to
        """

        sock.send(f"{self._method.value} {self._path} {WebClient.VERSION}\r\n".encode())

    def _send_headers(self, sock: EncryptedSocket) -> None:
        """Sends all defined headers

        Args:
            sock (EncryptedSocket): The socket to send to
        """

        for k, v in self._headers.items():
            sock.send(f"{k}: {str(v)}\r\n".encode())

    def _send_secure(self, sock: EncryptedSocket) -> None:
        """Sends the `SECURE` protocol request

        Args:
            sock (EncryptedSocket): The socket to change the protocol of
        """

        dh = DHClient()

        # Sends the first HTTP/1.1 request with the `SECURE` method
        # and the value of `e` used in the DH key exchange
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

        # Receives the response for the secure request
        # and reads the transmitted value of `f`
        secure_resp = ClientResponse(sock, True)
        dh.read_f(int(str(secure_resp.get_header("DH-F"))))
        LOG.debug("Finished SECURE handshake with %s, changing encryption", self._ip)

        # Updates the encryption of the socket to use the key `K`
        # generated by the DH key exchange
        sock.update_encryption(
            AesEncryption(
                dh.make_enc_key(AesEncryption.key_len()),
                dh.make_iv_str(AesEncryption.iv_len()),
            )
        )

    def _send_request(self, sock: EncryptedSocket) -> None:
        """Sends the user-defined request

        Args:
            sock (EncryptedSocket): The socket to send to
        """

        # Adds the `Content-Type` and `Content-Length` headers when necessary
        has_body = self._method == WebMethod.POST or self._method == WebMethod.PUT
        if has_body:
            if self._data is None:
                self._data = (json.dumps(self._json).encode(), "application/json")

            self._headers["Content-Type"] = self._data[1]
            self._headers["Content-Length"] = len(self._data[0])

        # Sends the HTTP request and body if provided
        self._send_status(sock)
        self._send_headers(sock)
        sock.send(b"\r\n")

        if has_body:
            # Ignore warning for self._data maybe being None,
            # because it gets set in the IF statement above
            sock.send(self._data[0])  # type: ignore
        # Flush the last encrypted block using b'\0' padding
        sock.flush()

    def send(self) -> ClientResponse:
        """Send this request using everything set beforehand

        Returns:
            ClientResponse: The response of the server
        """

        LOG.debug(
            "Sending request of %s %s to %s:%d",
            self._method.value,
            self._path,
            self._ip,
            self._port,
        )
        # Creates socket and connects to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect((self._ip, self._port))
        enc_sock = EncryptedSocket(sock)

        # Sends the `SECURE` request when selected
        if self._secure:
            self._send_secure(enc_sock)

        # Sends the normal request using the already set encryption
        self._send_request(enc_sock)

        return ClientResponse(enc_sock)

    def _default_headers(self) -> dict[str, str]:
        """
        Returns:
            dict[str, str]: The default headers to add to every request
        """

        return {
            "Accept": "*/*",
            # TODO maybe Accept-Encoding
            "Cache-Control": "no-cache",
            "User-Agent": f"JoaNetAPI/{locations.VERSION}",
        }
