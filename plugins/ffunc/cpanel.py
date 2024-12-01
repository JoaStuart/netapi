import os
import threading
from typing import Any

import pystray
from device.api import APIFunct
from device.device import DEV_PORT, FrontendDevice
from frontend.systray import SysTray
import locations
from pathlib import Path

from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
    QWebEngineUrlScheme,
)
from PyQt5.QtCore import QUrl, QByteArray, QBuffer


from proj_types.singleton import singleton
import utils
from webclient.client_request import WebClient, WebMethod


class CPanel(APIFunct):
    LOCALROOT = os.path.join(locations.PL_FFUNC, "cpanel")

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


class CPanelRequestScheme(QWebEngineUrlSchemeHandler):

    def requestStarted(self, request: QWebEngineUrlRequestJob | None) -> None:
        if not request:
            return

        resp = (
            WebClient(
                self._frontend._ip, DEV_PORT
            )  # TODO take from FrontendDevice's prepare method
            .set_path(f"/cpanel.{request.requestUrl().path()}")
            .set_secure(True)
            .set_method(WebMethod(request.requestMethod().data().decode().upper()))
            .authorize(FrontendDevice("")._token)
            .send()
        )

        data = resp.body
        mime = resp.get_header("Content-Type", "text/plain")

        self._data = QByteArray(data)

        buffer = QBuffer(request)
        buffer.setData(self._data)

        request.reply(QByteArray(mime), buffer)


@singleton
class CPanelBrowser(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("NetAPI Control Panel")

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        self.handler = CPanelRequestScheme()
        profile = QWebEngineProfile.defaultProfile()
        if profile:
            profile.installUrlSchemeHandler(b"cpanel", self.handler)

        self.browser.setUrl(QUrl("cpanel:///"))

    def show(self) -> None:
        pass


def open() -> None:
    app = QApplication([])
    panel = CPanelBrowser()
    panel.show()
    app.exec_()


SysTray().add_entry(
    pystray.MenuItem(
        "Open CPanel",
        lambda: threading.Thread(name="CPanelThread", target=open, daemon=True).start(),
    )
)
