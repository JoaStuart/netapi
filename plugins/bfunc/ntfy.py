import requests
import config
from device.api import APIFunct, APIResult


class Ntfy(APIFunct):
    def api(self) -> APIResult:
        body = {
            "topic": config.load("ntfy.default_topic", str),
            "title": "New notification!",
        } | self.body

        requests.post(
            f"http://{config.load("ntfy.ip", str)}:{config.load("ntfy.port", str)}/",
            json=body,
        )

        return APIResult.by_msg("Notification sent!")
