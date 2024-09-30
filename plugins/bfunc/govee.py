import base64
import json
import socket
from typing import Any
import config
from device.api import APIFunct
from webserver.webrequest import WebRequest


class GoveeLive:
    element_count = 36

    def __init__(self, parent) -> None:
        self.parent = parent
        parent._GoveeLight__send_instr("razer", {"pt": "uwABsQEK"})

    def new_cols(self) -> list[tuple[int, int, int]]:
        col_arr = []
        for _ in range(36):
            col_arr.append((0, 0, 0))
        return col_arr

    def __append_col(self, d: bytearray, col2: bool, col: tuple[int, int, int]) -> None:
        for c in col:
            d.append(c)
        d.append(2 if col2 else 1)

    def send_cols(self, col_arr: list[tuple[int, int, int]]) -> None:
        barr = bytearray(b"\xbb\x00\x86\xb4\x00")
        barr.append(self.element_count)
        idx = 0
        for _ in range(self.element_count):
            self.__append_col(barr, False, col_arr[idx])
            idx += 1

        self.parent.append_checksum(barr)

        self.parent._GoveeLight__send_instr(
            "razer", {"pt": base64.standard_b64encode(barr).decode()}
        )


class GoveeLight:
    def __init__(self, device_ip: str) -> None:
        self.ip = device_ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active_live = None

    def __send_packet(self, packet: dict) -> None:
        self.sock.sendto(json.dumps(packet).encode(), (self.ip, 4003))

    def __send_instr(self, cmd: str, data: dict) -> None:
        self.__send_packet({"msg": {"cmd": cmd, "data": data}})

    def power(self, on: bool) -> None:
        self.__send_instr("turn", {"value": 1 if on else 0})

    def brightness(self, brightness: int) -> None:
        self.__send_instr("brightness", {"value": min(max(1, brightness), 100)})

    def test(self) -> None:
        self.__send_instr("devStatus", {})

    def append_checksum(self, d: bytearray) -> None:
        check = 0
        for i in d:
            check ^= i
        d.append(check)

    def start_live(self) -> GoveeLive | None:
        if self.active_live == None:
            return GoveeLive(self)
        else:
            return None


class Govee(APIFunct):
    def __init__(
        self, request: WebRequest, args: list[str], body: dict[str, Any]
    ) -> None:
        super().__init__(request, args, body)
        self._govee = GoveeLight(str(config.load_var("govee.ip")))

    def api(self) -> dict | tuple[bytes, str]:
        if len(self.args) == 0:
            return {}

        match self.args[0]:
            case "on":
                self._govee.power(True)
            case "off":
                self._govee.power(False)
            case "bright":
                if len(self.args) == 2:
                    try:
                        self._govee.brightness(int(self.args[1]))
                    except ValueError:
                        return {"govee": "Brightness value must be an int"}
            case _:
                return {"govee": "SubFunction not found!"}
        return {}
