from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
    QWebEngineUrlScheme,
)
from PyQt5.QtCore import QUrl, QByteArray, QBuffer

from device.device import DEV_PORT, FrontendDevice
from frontend.systray import SysTray
import threading
from typing import Any
from webclient.client_request import WebClient, WebMethod
import pystray


from proj_types.singleton import singleton


class CPanelRequestScheme(QWebEngineUrlSchemeHandler):

    def requestStarted(self, request: QWebEngineUrlRequestJob | None) -> None:
        if not request:
            return

        resp = (
            FrontendDevice("")
            ._action_client(
                f"/cpanel.{request.requestUrl().path().replace(".", ":").replace("/", ".")}"
            )
            .set_method(WebMethod(request.requestMethod().data().decode().upper()))
            .send()
        )

        data = resp.body
        self._mime = resp.get_header("Content-Type", "text/plain")

        self._data = QByteArray(data)

        buffer = QBuffer(request)
        buffer.setData(self._data)

        request.reply(QByteArray(self._mime), buffer)


@singleton
class CPanelBrowser(QMainWindow):
    SCHEME = b"cpanel"

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("NetAPI Control Panel")

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)
        self.browser.showMaximized()

        self.handler = CPanelRequestScheme()
        profile = QWebEngineProfile.defaultProfile()
        if profile:
            profile.installUrlSchemeHandler(CPanelBrowser.SCHEME, self.handler)

        self.browser.load(QUrl("cpanel:///test.txt"))

    @staticmethod
    def register_scheme():
        scheme = QWebEngineUrlScheme(CPanelBrowser.SCHEME)
        scheme.setFlags(
            QWebEngineUrlScheme.SecureScheme | QWebEngineUrlScheme.LocalAccessAllowed
        )
        scheme.setSyntax(QWebEngineUrlScheme.Syntax.Path)
        scheme.setDefaultPort(80)
        QWebEngineUrlScheme.registerScheme(scheme)


def open() -> None:
    CPanelBrowser.register_scheme()
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
