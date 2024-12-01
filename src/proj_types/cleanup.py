import abc
import ctypes
from ctypes import wintypes
import logging
import os
import signal
from threading import Thread
from typing import NoReturn

from proj_types.event_type import EventType
from proj_types.singleton import singleton

LOG = logging.getLogger()


class CleanUp(abc.ABC):
    @abc.abstractmethod
    def cleanup(self) -> None:
        pass


if os.name == "nt":
    LRESULT = (
        ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    )

    WNDPROC = ctypes.WINFUNCTYPE(
        LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", ctypes.c_uint),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", wintypes.POINT),
        ]

    CW_USEDEFAULT = 0x80000000

    def WindowProc(hwnd, msg, wparam, lparam):
        match (msg):
            case 17:  # WM_QUERYENDSESSION
                return 1

            case 22:  # WM_ENDSESSION
                if lparam == 0:
                    from device.device import FrontendDevice

                    FrontendDevice("").dispatch_event(EventType.SHUTDOWN)

                return 0

            case _:
                return ctypes.windll.user32.DefWindowProcW(
                    hwnd, msg, wparam, wintypes.LPARAM(lparam)
                )


@singleton
class CleanupHandler:
    def __init__(self) -> None:
        self.CLEANUP_STACK: list[CleanUp] = []

    def handle_cleanup(self, *args, **kwargs) -> NoReturn:
        """Handle the cleanup upon any revieced signal"""

        LOG.info("Starting cleanup")

        for c in self.CLEANUP_STACK:
            c.cleanup()
        self.CLEANUP_STACK.clear()
        exit(0)

    def _windows_cleanup(self, event_type: int) -> bool:
        LOG.info("Windows cleanup")
        if event_type == 6:  # CTRL_SHUTDOWN_EVENT
            # Trigger shutdown event
            try:
                from device.device import FrontendDevice

                FrontendDevice("").dispatch_event(EventType.SHUTDOWN)
            except Exception:
                LOG.exception("Failed sending `SHUTDOWN` event!")

        self.handle_cleanup()
        return True

    def _register_lin(self) -> None:
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, self.handle_cleanup)

    def _register_win(self) -> None:
        self.winhandler = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(self._windows_cleanup)  # type: ignore

        kernel32 = ctypes.windll.kernel32  # type: ignore # Code only reachable on windows
        if not kernel32.SetConsoleCtrlHandler(self.winhandler, True):
            LOG.info(
                f"Registering windows cleanup callback failed with {hex(kernel32.GetLastError())}"
            )

        Thread(target=self._gdi_win, daemon=True, name="CtrlHandlerWindow").start()

    def _gdi_win(self) -> None:
        if os.name != "nt":
            return

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        RegisterClass = user32.RegisterClassW
        RegisterClass.argtypes = [ctypes.POINTER(WNDCLASS)]
        RegisterClass.restype = wintypes.ATOM

        CreateWindowEx = user32.CreateWindowExW
        CreateWindowEx.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        CreateWindowEx.restype = wintypes.HWND

        ShowWindow = user32.ShowWindow
        ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        ShowWindow.restype = wintypes.BOOL

        GetMessage = user32.GetMessageW
        GetMessage.argtypes = [
            ctypes.POINTER(MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        GetMessage.restype = wintypes.BOOL

        TranslateMessage = user32.TranslateMessage
        TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
        TranslateMessage.restype = wintypes.BOOL

        DispatchMessage = user32.DispatchMessageW
        DispatchMessage.argtypes = [ctypes.POINTER(MSG)]
        DispatchMessage.restype = LRESULT

        win = WNDCLASS()
        win.lpszClassName = "CtrlHandlerWindow"
        win.lpfnWndProc = WNDPROC(WindowProc)

        if not RegisterClass(ctypes.byref(win)):
            LOG.warning("Could not register window class")
            return

        hwnd = CreateWindowEx(
            0,
            win.lpszClassName,
            "CtrlHandlerWindow",
            0,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            0,
            0,
            0,
            0,
        )

        if not hwnd:
            LOG.warning("Could not create window")
            return

        ShowWindow(hwnd, 0)

        msg = MSG()
        while GetMessage(ctypes.byref(msg), None, 0, 0) > 0:
            TranslateMessage(ctypes.byref(msg))
            DispatchMessage(ctypes.byref(msg))

    def register(self) -> None:
        if os.name == "nt":
            self._register_win()
        else:
            self._register_lin()
