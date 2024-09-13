import select
import socket
import logging
from threading import Thread
from time import sleep
from typing import Type

from utils import CleanUp
from webserver.webrequest import WebRequest

LOG = logging.getLogger(__name__)


class WebServer(CleanUp):
    def __init__(self, port, handler: Type[WebRequest] = WebRequest) -> None:
        self._started = False
        self._handler = handler
        self._hostname = "0.0.0.0"
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
                conn = None
                try:
                    readable, _, _ = select.select([self._socket], [], [], 0)
                    if self._socket not in readable:
                        sleep(0.1)
                        continue

                    conn, addr = self._socket.accept()
                    LOG.debug("Got request by %s", str(addr[0]))
                    request: WebRequest = self._handler(self, conn, addr)
                    request.read_headers()

                    if file := request.has_public():
                        Thread(
                            target=request.send_page,
                            args=(file,),
                            daemon=True,
                            name="StaticHTTP",
                        ).start()
                        continue

                    Thread(
                        target=request.evaluate, daemon=True, name="RequestHTTP"
                    ).start()
                except ConnectionAbortedError:
                    LOG.debug("Connection Aborted by %s:%s", str(addr[0]), str(addr[1]))
                    pass
                except Exception:
                    LOG.debug("Connection closed unexpectedly:", exc_info=True)
                    if conn != None:
                        conn.close()
        except KeyboardInterrupt:
            pass
        self._socket.close()
        LOG.info("Closed socket")

    def cleanup(self) -> None:
        self._started = False
