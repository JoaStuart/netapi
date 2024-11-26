import logging
import os
from typing import Any
import serial
import termios
from backend.output import OutputDevice
from backend.sensor import Sensor
import config
import locations
import utils

LOG = logging.getLogger()


class Plants(Sensor):
    COUNT = 2

    def __init__(self) -> None:
        super().__init__(30)

    def poll(self) -> None:
        port = str(config.load_var("plants.port"))
        f = open(port)
        attrs = termios.tcgetattr(f)
        attrs[2] = attrs[2] & termios.HUPCL
        termios.tcsetattr(f, termios.TCSAFLUSH, attrs)
        f.close()
        se = serial.Serial()
        se.baudrate = 9600
        se.port = port
        se.open()

        for k in range(3):
            se.write(b"c")
            se.flush()
            data = se.read_until().decode().strip()
            if data == "checkok":
                break
            if k == 2:
                LOG.warning("Arduino check not succeeded!")
                return

        se.write(b"r")
        se.flush()
        data = se.read_until().decode().strip().split(",")

        if len(data) != Plants.COUNT:
            LOG.warning("Arduino sent an unexpected amount of vars")
            return

        self.data = {str(k): float(data[k]) for k in range(Plants.COUNT)}

    def get_plant_data(self, pid: int) -> dict[str, Any]:
        if self.data == None:
            return {}

        pdata = self.data[str(pid)]
        critical = config.load_var("plants.critical")
        if not isinstance(critical, list):
            LOG.warning("config::plants.critical must be list[float]")
            return {}

        names = config.load_var("plants.names")
        if not isinstance(names, list):
            LOG.warning("config::plants.names must be list[str]")
            return {}

        pcrit = critical[pid]
        isok = pcrit < float(pdata)
        score = convert_to_score(pdata, pcrit)
        name = names[pid]

        return {"name": name, "score": score, "ok": isok}

    def to(self, device: OutputDevice, args: list[str]) -> None:
        if self.data == None:
            device.data = {"alert": "alert"}
            return

        selected_plants = []

        a = args if len(args) > 0 else [i for i in range(Plants.COUNT)]

        for arg in a:
            try:
                pid = int(arg)
                selected_plants.append(self.get_plant_data(pid))
            except (ValueError, IndexError):
                pass

        names = " | ".join([plant["name"] for plant in selected_plants])
        min_score = min(plant["score"] for plant in selected_plants)
        all_ok = all(plant["ok"] for plant in selected_plants)
        critical_plants = " and ".join(
            plant["name"] for plant in selected_plants if not plant["ok"]
        )

        if type(device).__name__ == "StreamDeck":
            impath = os.path.join(
                locations.RESOURCES,
                f"images/plant_{"green" if all_ok else "red"}.png",
            )

            device.data = {
                "image": utils.imgread_uri(impath),
                "title": f"{names}\n{min_score}",
                "alert": "ok",
            }
            return

        device.data["plants"] = {
            "name": names,
            "score": min_score,
            "ok": all_ok,
            "critical": critical_plants,
        }

    def __str__(self) -> str | None:
        if self.data == None:
            return None
        return str(self.data)


def convert_to_score(data: float, critical: float) -> int:
    # Ensure the sensor_value is not less than the critical_value
    if data <= critical:
        return 0

    # Calculate the overload level
    overload_level = (data - critical) / (1.0 - critical)

    # Ensure the overload_level does not exceed 1.0
    return int(min(overload_level, 1.0) * 100)
