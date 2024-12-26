from typing import Any
import cv2
from backend.output import OutputDevice
import config


class StreamDeck(OutputDevice):
    def api_resp(self) -> dict:
        sd = {}
        if "image" in self.data:
            sd["image"] = self.data["image"]
        if "title" in self.data:
            sd["title"] = self.data["title"]

        alerts = ["alert"]
        if config.load_var("sd.checkmark"):
            alerts.append("ok")

        if "alert" in self.data and self.data["alert"] in alerts:
            sd[self.data["alert"]] = True

        return {"streamdeck": sd}


sd = StreamDeck
