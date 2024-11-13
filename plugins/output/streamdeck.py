from typing import Any
import cv2
from backend.output import OutputDevice
from utils import img_b64


class StreamDeck(OutputDevice):
    def api_resp(self) -> dict:
        sd = {}
        if "image" in self.data:
            sd["image"] = self.data["image"]
        if "title" in self.data:
            sd["title"] = self.data["title"]
        if "alert" in self.data and self.data["alert"] in ["ok", "alert"]:
            sd[self.data["alert"]] = True

        return {"streamdeck": sd}


sd = StreamDeck
