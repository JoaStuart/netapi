import requests
import config
from device.api import APIFunct, APIResult


class Ntfy(APIFunct):
    def api(self) -> APIResult:
        body = {
            "topic": config.load_var("ntfy.default_topic"),
            "title": "New notification!",
        } | self.body

        requests.post(
            f"http://{config.load_var("ntfy.ip")}:{config.load_var("ntfy.port")}/",
            json=body,
        )

        return APIResult.by_msg("Notification sent!")
