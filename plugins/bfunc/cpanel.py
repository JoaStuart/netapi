import os

from device.api import APIFunct, APIResult
import locations
from pathlib import Path
import utils


class CPanel(APIFunct):
    LOCALROOT = os.path.join(locations.PL_FFUNC, "cpanel")

    def is_in_subdir(self, file: str) -> bool:
        file_path = Path(file).resolve()
        directory = Path(CPanel.LOCALROOT).resolve()

        return directory in file_path.parents

    def api(self) -> APIResult:
        path = "/".join(self.args).replace(":", ".")
        file = os.path.join(CPanel.LOCALROOT, path)
        if not (os.path.isfile(file) and self.is_in_subdir(file)):
            return APIResult.by_json(
                {"code": 404, "message": "File not found!"}, success=False
            )

        with open(file, "rb") as rf:
            return APIResult.by_data(
                rf.read(), utils.mime_by_ext(os.path.splitext(file)[1])
            )

    def permissions(self, _: int) -> int:
        return 100
