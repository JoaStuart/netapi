import ctypes
from device.api import APIFunct


class Lock(APIFunct):
    """Windows specific lock workstation function"""

    def api(self) -> dict | tuple[bytes, str]:
        ctypes.windll.user32.LockWorkStation()
        return {}
