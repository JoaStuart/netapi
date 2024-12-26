import base64
import json
import logging
import os
import socket
from typing import Any, Optional, Type, TypeVar

import requests
import config
from device.api import APIFunct, APIResult
from webserver.webrequest import WebRequest

LOG = logging.getLogger()


class GoveeParameter:
    @staticmethod
    def of(data: dict[str, Any]) -> "GoveeParameter":
        for k, v in GoveeParameter.instances().items():
            if k == data["dataType"]:
                return v(data)

        return GoveeParameter(data)

    @staticmethod
    def instances() -> "dict[str, Type[GoveeParameter]]":
        return {
            "ENUM": GoveeEnum,
        }

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __str__(self):
        return f"<GoveeParameter {self._data}"


class GoveeEnum(GoveeParameter):
    def __init__(self, data):
        super().__init__(data)

        self._options: dict[str, Any] = {}

        for k in data["options"]:
            self._options[k["name"]] = k["value"]

    def __getitem__(self, key: str) -> Any:
        return self._options[key]

    def __str__(self):
        return f"<GoveeParameter:ENUM {self._options}>"

    def __contains__(self, val: str) -> bool:
        return val in self._options


_T = TypeVar("_T", bound="GoveeParameter")


class GoveeCapability:
    def __init__(
        self, type: str, instance: str, parameter: dict[str, Any], device: "GoveeDevice"
    ):
        self._type = type
        self._instance = instance
        self._parameter = GoveeParameter.of(parameter)
        self._device = device

    @property
    def type(self) -> str:
        return self._type

    @property
    def instance(self) -> str:
        return self._instance

    def __str__(self):
        return f"<{self.type}:{self.instance}{self._parameter}>"

    def set(self, value: Any) -> dict[str, Any]:
        return self._device.set(self._type, self._instance, value)

    def parameter(self, expected: Type[_T]) -> _T:
        if not isinstance(self._parameter, expected):
            raise ValueError("Not expected parameter")

        return self._parameter


class GoveeCapabilityList:
    def __init__(self):
        self._capabilities: list[GoveeCapability] = []

    def append(self, capab: GoveeCapability):
        self._capabilities.append(capab)

    def __call__(self, type: str, instance: str) -> "GoveeCapabilityList":
        lst = GoveeCapabilityList()

        for c in self._capabilities:
            if (type is None or c.type == type) and (
                instance is None or c.instance == instance
            ):
                lst.append(c)

        return lst

    def __getitem__(self, idx: int) -> GoveeCapability:
        return self._capabilities[idx]

    def __len__(self) -> int:
        return len(self._capabilities)

    def __str__(self):
        return "\n".join([str(c) for c in self._capabilities])


class GoveeDevice:
    def __init__(self, sku: str, mac: str, name: str, type: str, api: "GoveeMain"):
        self._sku = sku
        self._mac = mac
        self._name = name
        self._type = type
        self._api = api

        self._capabilities: GoveeCapabilityList = GoveeCapabilityList()

    @property
    def mac(self) -> str:
        return self._mac

    @property
    def sku(self) -> str:
        return self._sku

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    @property
    def capabilities(self) -> GoveeCapabilityList:
        return self._capabilities

    def load_capability(self, capability: dict[str, Any]) -> None:
        self._capabilities.append(
            GoveeCapability(
                capability["type"],
                capability["instance"],
                capability["parameters"],
                self,
            )
        )

    def set(self, type: str, instance: str, value: Any) -> dict[str, Any]:
        return self._api.control(self, type, instance, value)


class GoveeMain:
    def __init__(self, api_token: str):
        self._api_token: str = api_token

    def _request(self, path: str, data: Optional[dict[str, Any]]) -> dict[str, Any]:
        url = f"https://openapi.api.govee.com{path}"
        headers = {"Govee-API-Key": self._api_token}
        if not data:
            return requests.get(url, headers=headers).json()

        headers["Content-Type"] = "application/json"
        return requests.post(url, json=data, headers=headers).json()

    def control(
        self, device: GoveeDevice, type: str, instance: str, value: Any
    ) -> dict[str, Any]:
        data = {
            "requestId": "0",
            "payload": {
                "sku": device.sku,
                "device": device.mac,
                "capability": {
                    "type": type,
                    "instance": instance,
                    "value": value,
                },
            },
        }

        return self._request("/router/api/v1/device/control", data)

    def list_devices(self) -> list[GoveeDevice]:
        resp = self._request("/router/api/v1/user/devices", None)

        devices: list[GoveeDevice] = []
        for device in resp["data"]:
            devices.append(
                d := GoveeDevice(
                    device["sku"],
                    device["device"],
                    device["deviceName"],
                    device["type"],
                    self,
                )
            )

            for c in device["capabilities"]:
                d.load_capability(c)

        return devices


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

    def check(self) -> bool:
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("", 4002))
        srv.settimeout(5)

        self.__send_instr("devStatus", {})

        try:
            while True:
                data, _ = srv.recvfrom(1024)

                jdata = json.loads(data)
                msg = jdata.get("msg", {})
                if msg.get("cmd", "") == "devStatus":
                    return bool(msg.get("data", {}).get("onOff", 0))
        except socket.timeout:
            LOG.info("Govee device did not respond!")
        finally:
            srv.close()

        return False

    def append_checksum(self, d: bytearray) -> None:
        check = 0
        for i in d:
            check ^= i
        d.append(check)


class Govee(APIFunct):
    def __init__(
        self, request: WebRequest, args: list[str], body: dict[str, Any]
    ) -> None:
        super().__init__(request, args, body)
        self._govee = GoveeLight(str(config.load_var("govee.ip")))

    def api(self) -> APIResult:
        if len(self.args) == 0:
            return APIResult.by_success(False)

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
                        return APIResult.by_msg(
                            "Brightness value must be an int", success=False
                        )
            case "status":
                status = self._govee.check()
                return APIResult.by_msg(
                    f"Device {"on" if status else "off"}", success=status
                )
            case "scene":
                if len(self.args) < 2:
                    return APIResult.by_msg("You must provide a scene!", success=False)

                api = GoveeMain(os.environ["GOVEE_API"])
                device = api.list_devices()[0]
                capability = device.capabilities(
                    "devices.capabilities.dynamic_scene", "snapshot"
                )[0]
                parameter = capability.parameter(GoveeEnum)

                if self.args[1] not in parameter:
                    return APIResult.by_msg("Scene not found!", success=False)

                capability.set(parameter[self.args[1]])
            case _:
                return APIResult.by_msg("SubFunction not found!", success=False)
        return APIResult.by_success(True)
