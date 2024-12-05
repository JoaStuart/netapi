import pyperclip
from device.api import APIFunct, APIResult


class Paste(APIFunct):
    """Paste clipboard into response body"""

    def api(self) -> APIResult:
        return APIResult.by_msg(pyperclip.paste())


class Copy(APIFunct):
    """Copy data from request body into clipboard"""

    def api(self) -> APIResult:
        if "copy" in self.body:
            pyperclip.copy(self.body["copy"])
            return APIResult.by_success(True)
        return APIResult.by_msg("No data provided to copy.", success=False)
