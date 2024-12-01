import logging
import os
import cv2
import numpy as np
import requests
from backend.event import Event
from backend.interval import DailyExecutor, UnixExecutor
from backend.output import OutputDevice
from backend.sensor import Sensor
import locations
from proj_types.event_type import EventType
import utils

LOG = logging.getLogger()


class Wttr(Sensor):
    def __init__(self, repoll_after: float = 5) -> None:
        super().__init__(repoll_after)
        self.lat = 48.9333
        self.long = 9.7444

    def poll(self) -> None:
        cur_params = [
            "temperature_2m",
            "relative_humidity_2m",
            "is_day",
            "rain",
            "showers",
            "snowfall",
            "weather_code",
            "cloud_cover",
        ]

        req_params = [
            ("latitude", self.lat),
            ("longitude", self.long),
            ("current", ",".join(cur_params)),
            ("timeformat", "unixtime"),
            ("timezone", "Europe%2FBerlin"),
            ("forecast_days", "1"),
        ]

        url = "https://api.open-meteo.com/v1/forecast?"
        qry = "&".join([f"{k}={v}" for k, v in req_params])

        resp = requests.get(url + qry).json()

        self.data = resp["current"]

    def to(self, device: OutputDevice, args: list[str]) -> None:
        if self.data == None:
            return

        match type(device).__name__:
            case "StreamDeck":
                device.data = {
                    "title": f"{int(self.data["temperature_2m"])}°C",
                    "image": utils.img_b64(self._sd_ico()),
                    "alert": "ok",
                }
            case _:
                device.data["wttr"] = self.data

    def _ww_ico(self) -> str:
        if self.data == None:
            return ""

        ww = self.data["weather_code"]
        day = self.data["is_day"]

        if ww <= 0:
            return f"0{"d" if day else "n"}.png"
        if ww <= 2:
            return f"2{"d" if day else "n"}.png"
        if ww <= 3:
            return "3.png"
        if ww <= 45:
            return "45.png"
        if ww <= 51:
            return "51.png"
        if ww <= 56:
            return "56.png"
        if ww <= 61:
            return "61.png"
        if ww <= 66:
            return "66.png"
        if ww <= 71:
            return "71.png"
        if ww <= 77:
            return "77.png"
        if ww <= 80:
            return "80.png"
        if ww <= 85:
            return "85.png"
        if ww <= 95:
            return "95.png"
        return "96.png"

    def _sd_ico(self) -> cv2.typing.MatLike:
        bpath = os.path.join(locations.ROOT, "resources", "images", "wttr")
        bg = cv2.imread(os.path.join(bpath, "bg.png"), cv2.IMREAD_UNCHANGED)
        fg = cv2.imread(os.path.join(bpath, self._ww_ico()), cv2.IMREAD_UNCHANGED)
        bh, bw, bd = bg.shape
        fh, fw, fd = fg.shape

        off = (bh - fh) // 2
        y1, y2 = int(off // 1.5), int(off // 1.5) + fh
        x1, x2 = off, off + fw

        alpha_s = fg[:, :, 3] / 255.0
        alpha_l = 1.0 - alpha_s

        for c in range(0, 3):
            bg[y1:y2, x1:x2, c] = alpha_s * fg[:, :, c] + alpha_l * bg[y1:y2, x1:x2, c]

        return bg

    def __str__(self) -> str | None:
        if self.data == None:
            return None

        return str(self.data)


class SundownMaker(DailyExecutor):
    def __init__(self) -> None:
        super().__init__(self.on_trigger)

    def on_trigger(self) -> None:
        wttr = Wttr()
        wttr.poll()
        if wttr.data is None:
            return

        try:
            sunset = wttr.data["daily"]["sunset"][0]
        except KeyError:
            LOG.exception("Could not retrieve todays sunset")
            return

        UnixExecutor(sunset, self.on_sunset)

    def on_sunset(self) -> None:
        Event.trigger_all(EventType.SUNSET)
