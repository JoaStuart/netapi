import ctypes
from device.api import APIFunct, APIResult


class Lock(APIFunct):
    """Windows specific lock workstation function"""

    def api(self) -> APIResult:
        ctypes.windll.user32.LockWorkStation()
        return APIResult.by_success(True)
