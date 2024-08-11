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
from webserver.sitescript import load_script_file
from webserver.socketrequest import SocketRequest

LOG = logging.getLogger()


class WebResponse(ABC):
    def __init__(
        self,
        status_code: int = 500,
        status_msg: str = "NOT_IMPLEMENTED",
        headers: dict[str, str] = {},
        body: tuple[bytes, str] = (b"", "text/plain"),
    ) -> None:
        self._code = status_code
        self._msg = status_msg
        self._headers = headers
        self._body = body

    def code(self) -> int:
        return self._code

    def msg(self) -> str:
        return self._msg

    def headers(self) -> dict[str, str]:
        return self._headers

    def body(self) -> tuple[bytes, str]:
        return self._body


class WebRequest:
    def __init__(self, parent, conn: socket.socket, addr: tuple[str, int]) -> None:
        self._parent = parent
        self.path: str | None = None
        self.method: str | None = None
        self.version: str | None = None
        self._recv_headers: CaseInsensitiveDict[str] = CaseInsensitiveDict()
        self._recv_body: bytes | None = None
        self._get_args: dict[str, Any] = {}
        self._conn = conn
        self._addr = addr

        self.websocket_hndlr: Type[SocketRequest] | None = None

    def read_headers(self) -> None:
        r_bytes = self._conn.recv(2048)
        r_lines = r_bytes.decode("utf-8", "replace").split("\n")
        status = r_lines.pop(0).split(" ")
        self.method = status.pop(0)
        gargs = status.pop(0).split("?", 1)
        self.version = " ".join(status).strip()

        self.path = gargs[0]
        if len(gargs) > 1:
            for k in gargs[1].split("&"):
                if "=" not in k:
                    self._get_args[unquote(k.replace("+", " "))] = True
                else:
                    c, v = k.split("=", 1)
                    self._get_args[unquote(c.replace("+", " "))] = unquote(
                        v.replace("+", " ")
                    )

        try:
            while len(LINE := r_lines.pop(0)) > 0:
                s = LINE.strip().split(": ")
                if len(s) > 1:
                    key = s.pop(0)
                    self._recv_headers[key] = ": ".join(s)
                else:
                    self._recv_headers[s[0]] = ""
        except IndexError:
            pass

        METHOD = self.method.lower()
        if METHOD == "post" or METHOD == "put":
            self.read_body(r_bytes)

    def read_token(self) -> bool:
        try:
            tok = self._recv_headers.get("Authorization", None)
            if tok == None:
                return False
            tok = tok.removeprefix("BEARER ").strip()
            tokarr = [
                int(f"0x{tok[i]}{tok[i+1]}", base=16) for i in range(0, len(tok), 2)
            ]

            hip = hashlib.md5(self._addr[0].encode())
            hisset = True
            for h in hip.digest():
                if h + tokarr.pop(0) != 0xFF:
                    hisset = False

            return hisset
        except Exception:
            LOG.exception("Calculating TOKEN not successful")
            return False

    def read_body(self, r_bytes: bytes) -> None:
        try:
            if "Content-Length" in self._recv_headers:
                con_len = int(self._recv_headers["Content-Length"])
                if len(r_bytes) > con_len:
                    self._recv_body = r_bytes[len(r_bytes) - con_len :]
        except TypeError:
            LOG.debug("Browser sent non-int Content-Length")
            pass

    def send_response(self, code: int, message: str) -> None:
        self._conn.send(f"{self.version} {code} {message}\n".encode())

        self._default_headers()
        LOG.info(
            f"{code} [{message}] for {self.path} from {self._conn.getpeername()[0]} [{self.version}]"
        )

    def send_header(self, key: str, value: str) -> None:
        self._conn.send(f"{key}: {value}\n".encode())

    def end_headers(self) -> None:
        self._conn.send(b"\n")

    def send_body(self, body: bytes, c_type: str = "plain/text") -> None:
        if len(body) > 0:
            self.send_header("Content-Type", c_type)
            compressed = self._compress_body(body)

            self.send_header("Content-Length", f"{len(compressed)}")
            self.end_headers()

            self._conn.send(compressed)
            self._conn.close()

    def send_error(self, code: int, status: str, headers: list[tuple[str, str]] = []):
        self.send_response(code, status)
        self._default_headers()
        for hk, hv in headers:
            self.send_header(hk, hv)
        self.end_headers()
        self._conn.close()

    def _compress_body(self, orig: bytes) -> bytes:
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
                self.send_header("Content-Encoding", ", ".join(used))
            return body

    def has_public(self) -> str | None:
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
        try:
            p = os.path.join(PUBLIC, fname)
            name, ext = os.path.splitext(fname)

            if not os.path.isfile(p):
                self._respond(
                    WebResponse(
                        404,
                        "NOT_FOUND",
                        body=dumpb(
                            {"message": "The requested file could not be found!"}
                        ),
                    )
                )
                return

            mime = mime_by_ext(p)
            if os.path.isfile(os.path.join(PUBLIC, f"{name}.py")):
                LOG.debug("SiteScript file found")
                # SiteScript file exists and we can check format
                script = load_script_file(PUBLIC, f"{name}.py")
                if script != None:
                    s = script(self._get_args)
                    site_bin = s.site_read(p)
                    self._respond(WebResponse(200, "OK", body=(site_bin, mime)))
                    return
                LOG.debug("Not a SiteScript python file")

            with open(p, "rb") as rf:
                self._respond(WebResponse(200, "OK", body=(rf.read(), mime)))
        except Exception:
            LOG.exception("Exception while sending")

    def evaluate(self) -> None:
        if str(self._recv_headers.get("Upgrade", "")).lower() == "websocket":
            if self.websocket_hndlr == None:
                LOG.debug("Tried to connect WS without WS handler")
                self.send_error(400, "NO_WS_HNDLR")
            else:
                LOG.debug("WS connected")
                # TODO ws hndlr
                ws = self.websocket_hndlr(
                    self._parent,
                    self._conn,
                    self,
                    self._addr,
                    self._recv_headers,
                )
                ws.ws_init()
            return

        rs = None
        if self.method == None or self.path == None:
            return

        match self.method.lower():
            case "get":
                rs = self.REQUEST(self.path, self._get_args)
            case "post":
                rs = self.REQUEST(self.path, self._get_args | self._decode_body())
            case "options":
                self.do_OPTIONS()
                return
            case _:
                LOG.debug("Unknown method [%s]", self.method.lower())
                self.send_error(406, "METHOD_NOT_ALLOWED")
                return

        self._respond(rs or WebRequest(self, self._conn, self._addr))

    def _respond(self, resp: WebResponse) -> None:
        self.send_response(resp.code(), resp.msg())
        for k, v in resp.headers().items():
            self.send_header(k, v)
        self.send_body(*resp.body())
        self._conn.close()

    def _decode_body(self) -> dict:
        match str(self._recv_headers.get("Content-Type", "")).strip():
            case "application/json":
                b = (self._recv_body or b"").decode("utf-8", "replace")
                while not isinstance(b, dict):
                    b = json.loads(b)
                return b
            case _:
                LOG.error(
                    f"Body not recognized: {self._recv_headers.get("Content-Type", "")}"
                )
                return {}

    @abstractmethod
    def REQUEST(self, path: str, body: dict) -> WebResponse:
        raise NotImplementedError()

    def do_OPTIONS(self) -> None:
        self.send_response(204, "OPTIONS")
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.end_headers()
        self._conn.close()

    def _default_headers(self) -> None:
        self.send_header("Server", "JoaNetAPI")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
