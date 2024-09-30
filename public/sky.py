import os
from typing import Any

import cv2
import config
import locations
from webserver.sitescript import SiteScript


class PublicSky(SiteScript):
    SAVE_FOLDER: str = config.load_var("sky.save_folder")  # type: ignore
    WIDTH: int = config.load_var("sky.width")  # type: ignore
    HEIGHT: int = config.load_var("sky.height")  # type: ignore

    def display(self) -> None:
        self.headers |= {"Content-Disposition": 'attachment; filename="sky.mp4"'}

        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            os.path.join(locations.PUBLIC, "sky.mp4"),
            fourcc,
            24.0,
            (self.WIDTH, self.HEIGHT),
        )
        files = self._images()
        files.sort(key=lambda x: int(x.split(".")[0]))

        for f in files:
            im = cv2.imread(os.path.join(self.SAVE_FOLDER, f))
            writer.write(im)

        writer.release()

    def _images(self) -> list[str]:
        return [f for f in os.listdir(self.SAVE_FOLDER) if f.endswith(".jpg")]
