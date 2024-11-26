import requests
import config
from device.api import APIFunct


class Ntfy(APIFunct):
    def api(self) -> dict | tuple[bytes, str]:
        body = {
            "topic": config.load_var("ntfy.default_topic"),
            "title": "New notification!",
        } | self.body

        requests.post(
            f"http://{config.load_var("ntfy.ip")}:{config.load_var("ntfy.port")}/",
            json=body,
        )

        return {"ntfy": "Notification sent!"}
