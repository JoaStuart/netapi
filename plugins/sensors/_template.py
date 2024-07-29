from backend.output import OutputDevice
from backend.sensor import Sensor


class TemplateSensor(Sensor):
    def poll(self) -> None:
        # Poll data from sensor
        self.data = {"foo": "bar", "test": 1234}

    def to(self, device: OutputDevice) -> None:
        match type(device).__name__:
            case "StreamDeck":
                device.data = {"title": self.data["test"]}
            case _:
                device.data = self.data

    def __str__(self) -> str | None:
        return str(self.data)
