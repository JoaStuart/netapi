import select
import socket
import logging
from threading import Thread
from time import sleep
from typing import Any, Type

from types.cleanup import CleanUp
from webserver.webrequest import WebRequest

LOG = logging.getLogger()


class WebServer(CleanUp):
    def __init__(
        self, port, handler: Type[WebRequest] = WebRequest, args: dict[str, Any] = {}
    ) -> None:
        self._started = False
        self._handler = handler
        self._handler_args = args
        self._hostname = "0.0.0.0"
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self._hostname, self._port))

    def start_blocking(self) -> None:
        """Starts the server in the current thread"""

        self._socket.listen()
        self._started = True
        self._listen()

    def start(self) -> None:
        """Start the server in a background thread"""

        Thread(
            target=self.start_blocking,
            daemon=True,
            name="Listener",
        ).start()

    def _listen(self) -> None:
        """Main method for the listening thread"""

        try:
            while self._started:
                try:
                    readable, _, _ = select.select([self._socket], [], [], 0)
                    if self._socket not in readable:
                        sleep(0.1)
                        continue

                    conn, addr = self._socket.accept()
                    self._handle(conn, addr)
                except Exception:
                    LOG.debug("Exception while recieving", exc_info=True)
        except KeyboardInterrupt:
            pass
        self._socket.close()
        LOG.info("Closed socket")

    def _handle(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        try:
            LOG.debug("Got request by %s", str(addr[0]))
            request: WebRequest = self._handler(self, conn, addr, self._handler_args)
            request.read_headers()

            if file := request.has_public():
                Thread(
                    target=request.send_page,
                    args=(file,),
                    daemon=True,
                    name="StaticHTTP",
                ).start()
                return

            Thread(target=request.evaluate, daemon=True, name="RequestHTTP").start()
        except ConnectionAbortedError:
            LOG.debug("Connection Aborted by %s:%s", str(addr[0]), str(addr[1]))
        except Exception:
            LOG.debug("Connection closed unexpectedly:", exc_info=True)
            if conn != None:
                conn.close()

    def cleanup(self) -> None:
        self._started = False
