import pyperclip
from device.api import APIFunct


class Paste(APIFunct):
    """Paste clipboard into response body"""

    def api(self) -> dict | tuple[bytes, str]:
        return {"paste": pyperclip.paste()}


class Copy(APIFunct):
    """Copy data from request body into clipboard"""

    def api(self) -> dict | tuple[bytes, str]:
        if "copy" in self.body:
            pyperclip.copy(self.body["copy"])
            return {}
        return {"copy": "No data provided to copy."}
