import select
import socket
import logging
from threading import Thread
from time import sleep
from typing import Type

from utils import CleanUp
from webserver.webrequest import WebRequest

log = logging.getLogger()


class WebServer(CleanUp):
    def __init__(self, port, handler: Type[WebRequest] = WebRequest) -> None:
        self._started = False
        self._handler = handler
        self._hostname = "0.0.0.0"
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((self._hostname, self._port))

    def start_blocking(self) -> None:
        self._socket.listen()
        self._started = True
        self._listen()

    def start(self) -> None:
        Thread(
            target=self.start_blocking,
            daemon=True,
            name="Listener",
        ).start()

    def _listen(self) -> None:
        try:
            while self._started:
                conn = None
                try:
                    readable, _, _ = select.select([self._socket], [], [], 0)
                    if self._socket not in readable:
                        sleep(0.1)
                        continue

                    conn, addr = self._socket.accept()
                    log.debug("Got request by %s", str(addr[0]))
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
                    log.debug("Connection Aborted by %s:%s", str(addr[0]), str(addr[1]))
                    pass
                except Exception:
                    log.debug("Connection closed unexpectedly:", exc_info=True)
                    if conn != None:
                        conn.close()
        except KeyboardInterrupt:
            self._socket.close()
            return

    def cleanup(self) -> None:
        self._started = False
