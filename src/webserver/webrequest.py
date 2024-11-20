from abc import ABC, abstractmethod
import json
import os
import socket
import logging
import hashlib
from typing import Any, Type
from urllib.parse import unquote

from locations import PUBLIC
from utils import CaseInsensitiveDict, dumpb, mime_by_ext
from webserver.compression_util import ENCODINGS
from encryption.dh_key_ex import DHServer
from encryption.enc_socket import EncryptedSocket
from encryption.encryption import AesEncryption, Encryption
from webserver.sitescript import load_script_file

from log import LOG


class WebResponse(ABC):
    def __init__(
        self,
        status_code: int = 500,
        status_msg: str = "NOT_IMPLEMENTED",
        headers: dict[str, str] = {},
        body: tuple[bytes, str] = (b"", "text/plain"),
        keep_alive: bool = False,
    ) -> None:
        self._code = status_code
        self._msg = status_msg
        self._headers = headers
        self._body = body
        self._keep_alive = keep_alive

    @property
    def code(self) -> int:
        return self._code

    @property
    def msg(self) -> str:
        return self._msg

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def body(self) -> tuple[bytes, str]:
        return self._body

    @property
    def keep_alive(self) -> bool:
        return self._keep_alive

    def __str__(self) -> str:
        return f"<WebResponse code={self._code} msg={self._msg}>"


class WebRequest:
    def __init__(
        self, parent, conn: socket.socket, addr: tuple[str, int], args: dict[str, Any]
    ) -> None:
        self._parent = parent
        self.path: str | None = None
        self.method: str | None = None
        self.version: str | None = None
        self._recv_headers: CaseInsensitiveDict[str] = CaseInsensitiveDict()
        self._recv_body: bytes | None = None
        self._get_args: dict[str, Any] = {}
        self._conn = EncryptedSocket(conn)
        self._addr = addr
        self._args = args

    def _read_line(self) -> str:
        buff = []

        while (c := self._conn.recv(1)) != b"\n":
            buff.append(c)

        return (b"".join(buff) + b"\n").decode(errors="ignore")

    def read_headers(self) -> None:
        """Read all headers from the socket"""

        status = self._read_line().split(" ")
        self._parse_status(status)

        try:
            while len(LINE := self._read_line().strip()) > 0:
                s = LINE.strip().split(": ")
                if len(s) > 1:
                    key = s.pop(0)
                    self._recv_headers[key] = ": ".join(s)
                else:
                    self._recv_headers[s[0]] = ""
        except IndexError:
            pass

        METHOD = self.method.lower()  # type: ignore | self.method is never none here, because of the self._parse_status(...) call
        if METHOD == "post" or METHOD == "put":
            self._read_body()

    def _parse_status(self, status: list[str]) -> None:
        LOG.debug("Request for %s", str(status))
        self.method = status.pop(0)
        gargs = status.pop(0).split("?", 1)
        self.version = " ".join(status).strip()

        self.path = gargs[0]

        # Decode GET arguments
        if len(gargs) > 1:
            for k in gargs[1].split("&"):
                if "=" not in k:
                    self._get_args[unquote(k.replace("+", " "))] = True
                else:
                    c, v = k.split("=", 1)
                    self._get_args[unquote(c.replace("+", " "))] = unquote(
                        v.replace("+", " ")
                    )

    def _read_body(self) -> None:
        """Reads the body from the bytes object"""

        try:
            if "Content-Length" in self._recv_headers:
                con_len = int(self._recv_headers["Content-Length"])
                self._recv_body = self._conn.recv(con_len)
        except TypeError:
            LOG.warning("Browser sent non-int Content-Length")
            self._send_response(WebResponse(400, "NON_INT_CONTENT_LENGTH"))

    def _send_response(self, response: WebResponse) -> None:
        """Send a response based on a code and message

        Args:
            response (WebResponse): The HTTP response code
            message (str): The status message of the response
        """

        LOG.info(
            f"{response.code} [{response.msg}] for {self.path} from {self._conn.sock().getpeername()[0]} [{self.version}]"
        )
        self._conn.send(f"{self.version} {response.code} {response.msg}\n".encode())
        self._default_headers()

        for k, v in response.headers.items():
            self._send_header(k, v)

        self._send_body(*response.body, response.keep_alive)

    def _send_header(self, key: str, value: str) -> None:
        """Send one header

        Args:
            key (str): The key of the header
            value (str): The value of the header
        """

        self._conn.send(f"{key}: {value}\n".encode())

    def _end_headers(self) -> None:
        """End the headers for this response"""

        self._conn.send(b"\n")

    def _send_body(
        self, body: bytes, c_type: str = "plain/text", keep_alive: bool = False
    ) -> None:
        """Send the body of the request

        Args:
            body (bytes): The body object in bytes or b"" for no body
            c_type (str, optional): The `Content-Type` of the body. Defaults to "plain/text".
        """

        if len(body) == 0:
            self._end_headers()
            self._conn.flush()
            if not keep_alive:
                self._conn.close()
            return

        self._send_header("Content-Type", c_type)
        compressed = self._compress_body(body)

        self._send_header("Content-Length", f"{len(compressed)}")
        self._end_headers()

        self._conn.send(compressed)
        self._conn.flush()
        if not keep_alive:
            self._conn.close()

    def _compress_body(self, orig: bytes) -> bytes:
        """Tries to compress the body using the encodings provided in the request

        Args:
            orig (bytes): The body object as bytes

        Returns:
            bytes: The encoded body or the original body depending on the `Accept-Encoding` and length
        """

        if "accept-encoding" not in self._recv_headers:
            return orig
        body = orig
        accepts = str(self._recv_headers.get("Accept-Encoding", "")).split(", ")
        used = []
        for name, func in ENCODINGS:
            if name in accepts:
                body = func(body)
                used.append(name)

        if len(orig) <= len(body):
            return orig
        else:
            if len(used) > 0:
                self._send_header("Content-Encoding", ", ".join(used))
            return body

    def has_public(self) -> str | None:
        """Checks if there is a public file for the requested path

        Returns:
            str | None: The file path of the public file if existent or `None`
        """

        if self.path == None:
            return None
        for f in os.listdir(PUBLIC):
            name, ext = os.path.splitext(f)
            if (
                self.path.strip("/").lower() in [name.lower(), f.lower()]
                and ext.lower() != "py"
            ):
                return f

        return None

    def send_page(self, fname: str) -> None:
        """Sends the contents in the provided file and searches for SiteScripts of this file

        Args:
            fname (str): The path to the file
        """

        try:
            path = os.path.join(PUBLIC, fname)
            name, _ = os.path.splitext(fname)

            if not os.path.isfile(path):
                self._send_response(
                    WebResponse(
                        404,
                        "NOT_FOUND",
                        body=dumpb(
                            {"message": "The requested file could not be found!"}
                        ),
                    )
                )
                return

            mime = mime_by_ext(path)
            if self._load_sitescript(name, mime, path):
                return

            with open(path, "rb") as rf:
                self._send_response(WebResponse(200, "OK", body=(rf.read(), mime)))
        except Exception:
            LOG.exception("Exception while sending")

    def _load_sitescript(self, name: str, mime: str, path: str) -> bool:
        if os.path.isfile(os.path.join(PUBLIC, f"{name}.py")):
            LOG.debug("SiteScript file found")
            # SiteScript file exists and we can check format
            script = load_script_file(PUBLIC, f"{name}.py")
            if script != None:
                s = script(self._get_args)
                site_bin = s.site_read(path)
                self._send_response(
                    WebResponse(200, "OK", body=(site_bin, mime), headers=s.headers)
                )
                return True
            LOG.debug("Not a SiteScript python file")

        return False

    def evaluate(self) -> None:
        """Evaluates the request using the provided API request method"""

        if self.method == None or self.path == None:
            self._send_response(WebResponse(400, "NO_METHOD_OR_PATH"))
            return

        match self.method.lower():
            case "get":
                rs = self.do_GET()
            case "post":
                rs = self.do_POST()
            case "options":
                rs = self.do_OPTIONS()
            case "secure":
                return self.do_SECURE()
            case _:
                LOG.warning("Unknown method [%s]", self.method.lower())
                rs = WebResponse(405, "METHOD_NOT_ALLOWED")

        self._send_response(rs)

    def _decode_body(self) -> dict:
        """Tries to decode the body as JSON

        Returns:
            dict: The JSON dict or and empty dict if body not JSON

        Notes:
            - We are only expecting a JSON body, so this should be ok.
            - We try to decode as JSON to make it easier to execute functions through CURL without needing to specify the Content-Type explicitly. This only works because we do not support anything else at this moment.
        """

        try:
            body = (self._recv_body or b"").decode()

            while not isinstance(body, dict):
                body = json.loads(body)
        except UnicodeDecodeError:
            pass
        except json.JSONDecodeError:
            pass
        else:
            return body

        # Either JSONDecodeError or UnicodeDecodeError hit
        LOG.info(
            "Could not decode body of type: %s",
            self._recv_headers.get("Content-Type", None),
        )
        return {}

    @abstractmethod
    def REQUEST(self, path: str, body: dict) -> WebResponse:
        """Main API request method

        Args:
            path (str): The requested path
            body (dict): The body provided (or an empty dict if none is provided or body is not in JSON format)

        Returns:
            WebResponse: The object to respond with
        """

        pass

    def do_GET(self) -> WebResponse:
        """Default implementation for a `GET` request

        Returns:
            WebResponse: The response to reply with
        """

        return self.REQUEST(self.path or "/", self._get_args)

    def do_POST(self) -> WebResponse:
        """Default implementation for a `POST` request

        Returns:
            WebResponse: The response to reply with
        """

        return self.REQUEST(self.path or "/", self._get_args | self._decode_body())

    def do_OPTIONS(self) -> WebResponse:
        """Default implementation for an `OPTIONS` request

        Returns:
            WebResponse: The response to reply with
        """

        return WebResponse(
            status_code=204,
            status_msg="OPTIONS",
            headers={"Allow": "GET, POST, OPTIONS"},
        )

    def do_SECURE(self) -> None:
        # Perform the DH Key Exchange

        dh = DHServer()
        dh.read_e(int(self._recv_headers["DH-E"]))
        self._send_response(
            WebResponse(
                101, "SECURE", headers={"DH-F": str(dh.get_f())}, keep_alive=True
            )
        )

        # Create the encryption
        key = dh.make_enc_key(AesEncryption.key_len())
        iv = dh.make_iv_str(AesEncryption.iv_len())
        self._conn.update_encryption(AesEncryption(key, iv))

        # Read the actual encrypted HTTP request
        self.read_headers()
        self.evaluate()

    def _default_headers(self) -> None:
        """Default headers appended to every response"""

        self._send_header("Server", "JoaNetAPI")
        self._send_header("Access-Control-Allow-Origin", "*")
        self._send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self._send_header("Access-Control-Allow-Headers", "*")
