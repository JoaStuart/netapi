from abc import ABC, abstractmethod
import base64
import socket
import hashlib
import logging
import threading
from utils import CaseInsensitiveDict

log = logging.getLogger()


class WS:
    """Several constants used in WebSockets"""

    # WebSocket connection status
    CONNECTING = 0
    CONNECTED = 1
    CLOSING = 2
    CLOSED = 3

    # WebSocket OPCODE
    CONTINUE = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA

    # WebSocket close code
    CLOSE_NORMAL = 1000
    CLOSE_GOING_AWAY = 1001
    CLOSE_PROTO_ERR = 1002
    CLOSE_UNACC_DATA = 1003
    CLOSE_NON_CONSISTENT = 1007
    CLOSE_POLICY = 1008
    CLOSE_TOO_BIG = 1009
    CLOSE_EXTENTION = 1010
    CLOSE_UNEXP_CONDITION = 1011


class SocketInFragment:
    def __init__(self, parent, conn: socket.socket) -> None:
        self._parent = parent
        self._conn = conn
        self.opcode = 0
        self.fin = False
        self.sys = True

        while self.sys:
            while not self.fin:
                self._recv()

            self.sys = not self.eval()

    def _recv(self) -> None:
        """Recieve a fragment from the incoming data"""

        indta = [int.from_bytes(self._conn.recv(1), byteorder="big") for _ in range(2)]

        self.fin = (indta[0] & 0b1000_0000) > 0
        self.rsv = (indta[0] & 0b0111_0000) >> 4
        opcode = indta[0] & 0b0000_1111
        if opcode > 0:
            self.opcode = opcode
        self.mask = (indta[1] & 0b1000_0000) > 0

        pfirst = indta[1] & 0b0111_1111
        if pfirst <= 125:
            self.pload_len = pfirst
        elif pfirst == 126:
            self.pload_len = int.from_bytes(
                self._conn.recv(2), byteorder="big", signed=False
            )
        else:
            self.pload_len = int.from_bytes(
                self._conn.recv(8), byteorder="big", signed=False
            )
            if self.pload_len > 0x7FFFFFFFFFFFFFFF:
                self._parent.close(
                    WS.CLOSE_PROTO_ERR, "Invalid length (MSB of 64bit len SET)"
                )

        if self.mask:
            self.mask_key = [int.from_bytes(bytes([i])) for i in self._conn.recv(4)]

        self.payload = self._conn.recv(self.pload_len)
        if self.mask:
            self.payload = bytes(
                [
                    self.payload[i] ^ self.mask_key[i % 4]
                    for i in range(len(self.payload))
                ]
            )

    def eval(self) -> bool:
        """Evaluate the recieved packet and respond if neccecary

        Returns:
            bool: Whether the packet should be forwarded to the user
        """
        match self.opcode:
            case WS.CONTINUE:
                # Fuck we missed sth
                log.error("Continuation without message begin")
                return False
            case WS.TEXT:  # Got text data
                try:
                    self.payload = self.payload.decode()
                except UnicodeDecodeError:
                    self._parent.close(WS.CLOSE_NON_CONSISTENT, "UnicodeDecodeError")
            case WS.CLOSE:  # Got close request
                self._parent.send(WS.CLOSE, self.payload)
                return False
            case WS.PING:  # Got ping, respond with pong
                self._parent.send(0xA, self.payload)
                return False
            case WS.PONG:  # Got pong
                return False

        return True


class SocketOutFragment:
    def __init__(self, conn: socket.socket, opcode: int) -> None:
        self._conn = conn
        self._opcode = opcode
        self.fin = False

    def send_fin(self, payload: bytes | str) -> None:
        """Sends a packet with the final bit set

        Args:
            payload (bytes | str): The payload to send as the body of the packet
        """

        self._send(True, payload)

    def send_part(self, payload: bytes | str) -> None:
        """Sends a packet without the final bit set. In order to finish sending the packet `SocketOutFragment::send_fin` should be used

        Args:
            payload (bytes | str): The payload to send as the partial body

        Notes:
            This packet needs to be finished using `SocketOutFragment::send_fin` before beginning a new packet
        """

        self._send(False, payload)

        self._opcode = 0x0  # Change to continuation OPCODE

    def _send(self, fin: bool, payload: bytes | str) -> None:
        """Sends the payload using a WebSocket packet

        Args:
            fin (bool): Whether this packet is final
            payload (bytes | str): The payload of the packet

        Raises:
            Exception: When recieving a packet with a length longer than `0x7FFFFFFFFFFFFFFF`
        """

        if isinstance(payload, str):
            payload = payload.encode()
        self.fin = fin

        sbuf = bytes()
        fbit = 0b1000_0000 if fin else 0
        # Generate first byte of MSG [FIN;RSV(3);OPCODE(4)]
        sbuf += (fbit | (self._opcode & 0b0000_1111)).to_bytes(1)

        # Encode payload length
        l = len(payload)
        if l <= 125:
            sbuf += l.to_bytes(1)
        elif l <= 0xFFFF:
            sbuf += (126).to_bytes(1)
            sbuf += l.to_bytes(2, signed=False)
        elif l <= 0x7FFFFFFFFFFFFFFF:
            sbuf += (127).to_bytes(1)
            sbuf += l.to_bytes(8, signed=False)
        else:
            raise Exception("Payload message too long")

        self._conn.sendall(sbuf + payload)


class SocketRequest(ABC):
    def __init__(
        self,
        parent,
        conn: socket.socket,
        web_req,
        addr: tuple[str, int],
        recv_headers: CaseInsensitiveDict[str],
    ) -> None:
        self._parent = parent
        self._conn = conn
        self._status = WS.CONNECTING
        self._web_req = web_req
        self._addr = addr
        self._recv_headers = recv_headers
        self._in_evt = threading.Event()
        self._in_buff: list[SocketInFragment] = []
        self._cur_out: SocketOutFragment | None = None

    def _recv_thread(self) -> None:
        """Starts the receiving thread"""

        try:
            while self._status != WS.CLOSED:
                self._in_buff.append(SocketInFragment(self, self._conn))
                self._in_evt.set()
        except ConnectionResetError:
            pass

    def ws_init(self) -> None:
        """Initializes the WebSocket

        Raises:
            Exception: Socket closed when trying to switch
        """

        if self._status != WS.CONNECTING:
            raise Exception("Socket not in CONNECTING state!")

        if (
            str(self._recv_headers.get("Connection", "")).lower() != "upgrade"
            or str(self._recv_headers.get("Upgrade", "")).lower() != "websocket"
        ):
            self._parent.send_error(400, "INV_HEADER")
            return

        try:
            ver = int(self._recv_headers.get("Sec-WebSocket-Version") or "")
            if ver != 13:
                raise ValueError()
        except ValueError:
            self._web_req.send_error(400, "BAD_VER", [("Sec-WebSocket-Version", "13")])
            return

        key = self._recv_headers.get("Sec-WebSocket-Key", "")
        conc_key = (key or "") + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        b64_resp = base64.standard_b64encode(hashlib.sha1(conc_key.encode()).digest())

        self._web_req.send_response(101, "Switching Protocols")
        self._web_req.send_header("Upgrade", "websocket")
        self._web_req.send_header("Connection", "Upgrade")
        self._web_req.send_header("Sec-WebSocket-Accept", b64_resp.decode())
        self._web_req.end_headers()

        self._status = WS.CONNECTED

        threading.Thread(target=self._recv_thread, daemon=True).start()

        try:
            self.on_connect()
        except ConnectionAbortedError:
            pass

    def recv(self, timeout: float | None = None) -> SocketInFragment | None:
        """Recieves a SocketInFragment from the socket

        Args:
            timeout (float | None, optional): The maximum timeout before returning. Defaults to None.

        Raises:
            Exception: Socket closed without a close packet

        Returns:
            SocketInFragment | None: The fragment read or None if the timeout is reached
        """

        if self._status == WS.CLOSED and len(self._in_buff) == 0:
            raise Exception("No more data can be read because socket is closed!")

        if not self._in_evt.wait(timeout=timeout):
            return None

        msg = self._in_buff.pop(0)
        if len(self._in_buff) == 0:
            self._in_evt.clear()
        return msg

    def create_out(self, opcode: int) -> SocketOutFragment:
        """Creates a SocketOutFragment

        Args:
            opcode (int): The opcode of this packet (See `WS` for constants)

        Raises:
            Exception: When the socket closed or an unfinished packet is present

        Returns:
            SocketOutFragment: The created SocketOutFragment
        """

        if not (self._status == WS.CONNECTED or self._status == WS.CLOSING):
            raise Exception(
                f"Connection not ready for data to be sent! [{self._status}]"
            )
        if self._cur_out != None and not self._cur_out.fin:
            raise Exception("Non-finished outgoing message present")

        self._cur_out = SocketOutFragment(self._conn, opcode & 0x0F)
        return self._cur_out

    def send(self, opcode: int, payload: bytes | str) -> None:
        """Sends a packet

        Args:
            opcode (int): The opcode of this packet (See `WS` for constants)
            payload (bytes | str): The payload of the packet

        Raises:
            Exception: When the connection isn't ready for packets yet
        """

        if not (self._status == WS.CONNECTED or self._status == WS.CLOSING):
            raise Exception(
                f"Connection not ready for data to be sent! [{self._status}]"
            )
        o = self.create_out(opcode)
        o.send_fin(payload)

    @abstractmethod
    def on_connect(self) -> None:
        """Method that gets called upon the connection of a WebSocket"""

        pass

    def close(self, status: int = 1000, message: str = "") -> None:
        """Sends a closing packet and closes the WebSocket

        Args:
            status (int, optional): The closing status (see `WS` for constants). Defaults to WS.CLOSE_NORMAL.
            message (str, optional): The status message of this close. This message does not get displayed to the user! Defaults to "".
        """

        self.send(0x8, f"{status}{message}".encode())
        if self._status == WS.CLOSING:
            self._status = WS.CLOSED
            self._conn.close()
        else:
            self._status = WS.CLOSING
