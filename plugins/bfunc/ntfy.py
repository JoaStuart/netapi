import requests
import config
from device.api import APIFunct, APIResult


class Ntfy(APIFunct):
    def api(self) -> APIResult:
        body = {
            "topic": config.load_str("ntfy.default_topic"),
            "title": "New notification!",
        } | self.body

        requests.post(
            f"http://{config.load_str("ntfy.ip")}:{config.load_str("ntfy.port")}/",
            json=body,
        )

        return APIResult.by_msg("Notification sent!")
