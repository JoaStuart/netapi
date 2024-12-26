from enum import Enum
import json
import os
import sys
from typing import Any, Optional

import requests

BACKEND_IP = "192.168.188.49"


class Quickaction(Enum):
    GOVEE_ON = "/govee.on"
    GOVEE_OFF = "/govee.off"
    MEROSS_ON = "/meross.1.on"
    MEROSS_OFF = "/meross.1.off"
    LOCK = "/lock"

    @staticmethod
    def generate(ip: str) -> None:
        path = os.path.abspath(os.path.dirname(__file__))

        for name, _ in Quickaction._member_map_.items():
            if os.name == "nt":
                Quickaction.generate_bat(ip, path, name)
            elif os.name == "posix":
                Quickaction.generate_sh(ip, path, name)

    @staticmethod
    def generate_bat(ip: str, path: str, name: str) -> None:
        contents: list[str] = [
            "@echo off",
            "",
            f"cd {path}",
            f"python quickaction.py {ip} {name}",
            "exit",
            "",
        ]

        with open(os.path.join(path, f"{name}.bat"), "w") as wf:
            wf.write("\n".join(contents))

    @staticmethod
    def generate_sh(ip: str, path: str, name: str) -> None:
        contents: list[str] = [
            "#!/bin/bash",
            "",
            f"cd {path}",
            f"python3 quickaction.py {ip} {name}",
            "exit" "",
        ]

        with open(os.path.join(path, f"{name}.sh"), "w") as wf:
            wf.write("\n".join(contents))

    def __init__(self, action: str) -> None:
        self._action = action

    def _load_config(self) -> dict[str, Any]:
        file_path = os.path.dirname(__file__)
        root_path = os.path.join(file_path, "..", "..")
        config_path = os.path.join(root_path, "config.json")

        with open(config_path, "r") as rf:
            data = json.loads(rf.read())

        return data

    def _load_token(self, config: dict[str, Any]) -> str:
        subdevices = config.get("subdevices", None)

        if subdevices is None:
            raise ValueError("No subdevices found!")

        subdev = None
        for s in subdevices:
            if s.get("name", None) == "__QUICKACTION":
                subdev = s

        if subdev is None:
            raise ValueError("The subdevice `__QUICKACTION` could not be found!")

        return subdev.get("token", "")

    def perform_action(self, backip: str, port: int = 4001) -> Optional[dict[str, Any]]:
        config = self._load_config()
        token = self._load_token(config)

        response = requests.get(
            f"{backip}:{port}{self._action}",
            headers={"Authorization": f"BEARER {token}"},
        )

        try:
            return response.json()
        except Exception:
            pass


if __name__ == "__main__":
    ip = sys.argv[1]
    action = sys.argv[2]
    action_cls = Quickaction(action)
    print(f"Response: {json.dumps(action_cls.perform_action(ip), indent=4)}")
