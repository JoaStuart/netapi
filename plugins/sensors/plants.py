import logging
import os
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

    def to(self, device: OutputDevice, args: list[str]) -> None:
        if self.data == None:
            device.data = {"alert": "alert"}
            return

        critical = config.load_var("plants.critical")
        if not isinstance(critical, list):
            LOG.warning("config::plants.critical must be list[float]")
            return

        match type(device).__name__:
            case "StreamDeck":
                ok, title = None, None

                try:
                    if len(args) > 0:
                        p = int(args[0])
                        if p >= 0 and p < Plants.COUNT:
                            ok = critical[p] < float(self.data[str(p)])
                            title = (
                                str(convert_to_score(self.data[str(p)], critical[p]))
                                + "\n"
                                + config.load_var("plants.names")[p]  # type: ignore
                            )
                except ValueError:
                    pass

                ok = ok or utils.tuple_lt(
                    tuple(critical),
                    tuple([self.data[str(k)] for k in range(Plants.COUNT)]),
                )
                t_scores = [
                    convert_to_score(self.data[str(k)], critical[k])
                    for k in range(Plants.COUNT)
                ]
                title = title or " | ".join(
                    [str(t_scores[i]) for i in range(Plants.COUNT)]
                )

                device.data = {
                    "title": title,
                    "image": utils.imgread_uri(
                        os.path.join(
                            locations.ROOT,
                            "resources",
                            "images",
                            f"plant_{"green" if ok else "red"}.png",
                        )
                    ),
                    "alert": "ok",
                }
            case _:
                device.data = self.data

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
