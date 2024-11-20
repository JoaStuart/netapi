import os
from typing import Any

import pystray
from device.api import APIFunct
from frontend.systray import SysTray
import locations
from pathlib import Path

from PyQt5.QtCore import QUrl, QByteArray
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineProfile
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView


from proj_types.singleton import singleton
import utils
from webserver.webrequest import WebRequest


class CPanel(APIFunct):
    LOCALROOT = os.path.join(locations.PL_FFUNC, "cpanel")

    def __init__(
        self, request: WebRequest | None, args: list[str], body: dict[str, Any]
    ) -> None:
        super().__init__(request, args, body)

        SysTray().add_entry(pystray.MenuItem("Open CPanel", CPanelBrowser().show()))

    def is_in_subdir(self, file: str) -> bool:
        file_path = Path(file).resolve()
        directory = Path(CPanel.LOCALROOT).resolve()

        return directory in file_path.parents

    def api(self) -> dict | tuple[bytes, str]:
        path = "/".join(self.args)
        file = os.path.join(CPanel.LOCALROOT, path)
        if not (os.path.isfile(file) and self.is_in_subdir(file)):
            return {"cpanel": {"code": 404, "message": "File not found!"}}

        with open(file, "rb") as rf:
            return (rf.read(), utils.mime_by_ext(os.path.splitext(file)[1]))

    def permissions(self, _: int) -> int:
        return 100


class CPanelInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info) -> None:
        url = info.requestUrl().toString()
        print(f"Intercepted {url}")


@singleton
class CPanelBrowser(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NetAPI Control Panel")

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        interceptor = CPanelInterceptor()
        QWebEngineProfile.defaultProfile().setRequestInterceptor(interceptor)

    def show(self) -> None:
        pass
