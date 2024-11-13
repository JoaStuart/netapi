import ctypes
import win32gui
import win32con
from typing import Any

from device.api import APIFunct
from webserver.webrequest import WebRequest


class Console(APIFunct):
    """Show/Hide attached Console on Windows using kernel32"""

    def __init__(
        self, request: WebRequest, args: list[str], body: dict[str, Any]
    ) -> None:
        super().__init__(request, args, body)
        self._shown = False

    def api(self) -> dict | tuple[bytes, str]:
        pid = ctypes.windll.kernel32.GetConsoleWindow()
        if pid == None:
            return {"console": "No associated Console window found!"}

        if self._shown:
            win32gui.ShowWindow(pid, win32con.SW_HIDE)
        else:
            win32gui.ShowWindow(pid, win32con.SW_SHOW)
        self._shown = not self._shown

        return {}
