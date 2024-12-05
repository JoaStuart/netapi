import io
import os
import cv2
import time
import logging
from threading import Thread

import requests

from backend.interval import TimedExecutor
import config
from device.api import APIFunct, APIResult
import locations

LOGGER = logging.getLogger()


class Sky(APIFunct):
    WIDTH: int = config.load_var("sky.width")  # type: ignore
    HEIGHT: int = config.load_var("sky.height")  # type: ignore
    CAMERA: int = config.load_var("sky.camera")  # type: ignore
    INTERVAL: int = config.load_var("sky.interval")  # type: ignore
    SAVE_TIME: int = config.load_var("sky.save_time")  # type: ignore
    SAVE_FOLDER = os.path.join(locations.ROOT, config.load_var("sky.save_folder"))  # type: ignore

    FULL = False
    EXECUTOR: TimedExecutor | None = None

    def api(self) -> APIResult:
        if len(self.args) > 0:
            match self.args[0].lower():
                case "stop":
                    return self.stop()
                case "start":
                    return self.start()
                case "preview":
                    return self.preview()
                case _:
                    return APIResult.by_msg("Method not found", success=False)

        return APIResult.by_json({"files": len(self._images())})

    def stop(self) -> APIResult:
        if Sky.EXECUTOR is not None:
            Sky.EXECUTOR.unregister()
            Sky.EXECUTOR = None

            return APIResult.by_msg("Stopped")
        return APIResult.by_msg("No instance running", success=False)

    def start(self) -> APIResult:
        if Sky.EXECUTOR is None:
            Sky.EXECUTOR = TimedExecutor(self.INTERVAL, self.take_picture)

            for f in self._images():
                os.remove(os.path.join(self.SAVE_FOLDER, f))

            return APIResult.by_msg("Started")
        return APIResult.by_msg("Instance already running", success=False)

    def preview(self) -> APIResult:
        cap = cv2.VideoCapture(self.CAMERA)
        if not cap.isOpened():
            return APIResult.by_msg("Camera could not be opened!", success=False)

        self._set_props(cap)

        result, image = cap.read()

        if not result:
            return APIResult.by_msg("Image could not be taken", success=False)

        result, buff = cv2.imencode(".jpg", image)

        if not result:
            return APIResult.by_msg("Image could not be encoded", success=False)

        return APIResult.by_data(buff.tobytes(), "image/jpeg")

    def _images(self) -> list[str]:
        return [f for f in os.listdir(self.SAVE_FOLDER) if f.endswith(".jpg")]

    def _clean_pictures(self) -> None:
        f_keep = self.SAVE_TIME - 1
        files = self._images()

        if len(files) <= f_keep:
            return

        if not self.FULL:
            self.FULL = True
            requests.post(
                "http://192.168.188.48:5105",
                json={
                    "topic": "joa",
                    "message": f"Video buffer filled with content from {self.SAVE_TIME * 10 / 60 / 60}h",
                    "title": "📁 ✅ Sky-buffer filled",
                    "priority": 4,
                },
            )

        files.sort(key=lambda x: int(x.split(".")[0]))
        files_to_delete = len(files) - f_keep

        for i in range(files_to_delete):
            file_to_delete = os.path.join(self.SAVE_FOLDER, files[i])
            os.remove(file_to_delete)

    def _set_props(self, cap) -> None:
        for n, i in {
            cv2.CAP_PROP_BRIGHTNESS: 128,
            cv2.CAP_PROP_CONTRAST: 32,
            cv2.CAP_PROP_EXPOSURE: 166,
            cv2.CAP_PROP_GAIN: 64,
            cv2.CAP_PROP_SATURATION: 32,
            cv2.CAP_PROP_TEMPERATURE: 5500,
            cv2.CAP_PROP_FRAME_WIDTH: self.WIDTH,
            cv2.CAP_PROP_FRAME_HEIGHT: self.HEIGHT,
        }.items():
            cap.set(n, i)

    def take_picture(self) -> None:
        # t = time.time() + self.TIMEZONE % 86400
        # if t < self.DAY_START or t > self.DAY_END:
        #     return

        self._clean_pictures()

        cap = cv2.VideoCapture(self.CAMERA)
        if not cap.isOpened():
            LOGGER.warning("Camera could not be opened!")
            return

        self._set_props(cap)

        result, image = cap.read()

        if not result:
            LOGGER.warning("Image could not be taken")
            self.stop()
            return

        f = os.path.join(locations.ROOT, f"../sky/{int(time.time() * 1000)}.jpg")
        cv2.imwrite(f, image)
        # LOGGER.info(f"Saving image {f}")
        cap.release()
