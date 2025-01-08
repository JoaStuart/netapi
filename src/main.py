import os
import socket
import sys
import time
import logging
import argparse
import traceback
from types import TracebackType
from typing import NoReturn, Type
from backend.automation import Automation
from backend.event import Event
from backend.multicast_srv import MulticastServer
import config
from device.device import DEV_PORT
from device.ntfy import NtfyAdapter
from frontend.multicast_cli import MulticastClient
from locations import VERSION
import locations
from proj_types.cleanup import CleanUp, CleanupHandler
from quickaction.quickaction import Quickaction
from webserver.webserver import WebServer


LOG = logging.getLogger()


CleanupHandler().register()


def setup_logger(verbose: bool) -> None:
    """Setup the logger for this project

    Args:
        verbose (bool): Whether verbose logging in enabled
    """

    logFormatter = logging.Formatter(
        "%(asctime)s :: %(funcName)s<@>%(threadName)s [%(levelname)-1.1s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    LOG.setLevel(logging.DEBUG)
    for h in LOG.handlers:
        LOG.removeHandler(h)

    logPath = os.path.join(locations.ROOT, "logs")
    logName = time.strftime("%Y-%m-%d %H-%M", time.localtime())

    for i in os.listdir(logPath):
        os.remove(os.path.join(logPath, i))

    fileHandler = logging.FileHandler(os.path.join(logPath, f"{logName}.log"))
    fileHandler.setLevel(logging.DEBUG)
    fileHandler.setFormatter(logFormatter)
    LOG.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setLevel(logging.DEBUG if verbose else logging.INFO)
    consoleHandler.setFormatter(logFormatter)
    LOG.addHandler(consoleHandler)


def restart() -> NoReturn:
    os.execl(sys.executable, "python", __file__, *sys.argv[1:])


def pack(name: str) -> None:
    LOG.info("Packing source...")
    zname = f"{locations.ROOT}{name}"
    locations.compress_pkg(zname)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "action",
        choices=["frontend", "backend", "pack"],
        default="backend",
        help="Choose to start backend or frontend",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return p.parse_args()


def update() -> None:
    for k in os.listdir(locations.ROOT):
        name, ext = os.path.splitext(k)
        if not name.startswith("netapi-"):
            continue

        v = float(name.split("-")[1])
        if v > VERSION:
            LOG.info(f"Updating netapi to version {v}...")
            locations.unpack(os.path.join(locations.ROOT, k))
            os.remove(os.path.join(locations.ROOT, k))

            restart()
            return 12


def frontend() -> None | int:
    from frontend.systray import SysTray, TrayState
    from device.device import FrontendDevice
    from frontend.frontend import FrontendRequest

    LOG.info("Starting [FRONTEND]...")

    # Start systray
    tray = SysTray()
    CleanupHandler().CLEANUP_STACK.append(tray)
    tray.start()

    # Get backend IP by Multicast
    mcast_client = MulticastClient()
    ip = mcast_client.request()
    if ip is None:
        LOG.warning("The server could not be found!")
        return 1

    # Log in and start frontend
    try:
        fdev = FrontendDevice(ip)
        CleanupHandler().CLEANUP_STACK.append(fdev)
        fdev.login(VERSION)
    except Exception:
        tray.update_icon(TrayState.FAILED)
        LOG.exception(f"Login failed at {ip}. Exiting...")
        time.sleep(2)
        CleanupHandler().CLEANUP_STACK.remove(fdev)
        return 1

    tray.update_icon(TrayState.CONNECTED)
    tray.handle_cleanup = CleanupHandler().handle_cleanup

    LOG.info("Generating QuickAction scripts...")
    Quickaction.generate(ip)

    LOG.info("Connected to backend")
    srv = WebServer(DEV_PORT, FrontendRequest, {"ip": ip})
    CleanupHandler().CLEANUP_STACK.append(srv)
    srv.start_blocking()


def backend() -> None | int:
    from backend.backend import DEVICES, BackendRequest

    LOG.info("Starting [BACKEND]...")
    # Start Multicast backend
    multi_server = MulticastServer()
    multi_server.background_listen()

    # start backend
    srv = WebServer(DEV_PORT, BackendRequest)
    CleanupHandler().CLEANUP_STACK.append(srv)

    class BC(CleanUp):
        def cleanup(self) -> None:
            for _, d in DEVICES.items():
                d.close()

    CleanupHandler().CLEANUP_STACK.append(BC())

    LOG.info("Started scheduler")

    Automation.load_all()
    LOG.info("Loaded automations")

    Event.load_all()
    LOG.info("Loaded events")

    srv.start_blocking()
    CleanupHandler().handle_cleanup()


def main() -> int:
    args = parse_args()

    setup_logger(args.verbose)

    locations.make_dirs()

    act = args.action
    ret = 0

    if act == "frontend":
        update()
        ret = frontend() or ret
    elif act == "backend":
        pack("/public/pack.zip")
        ret = backend() or ret

    return ret


def exception_hook(
    exc: Type[BaseException], value: BaseException, tb: TracebackType | None
):
    trace_str = "".join(traceback.format_exception(exc, value=value, tb=tb))
    LOG.exception(trace_str)

    (
        NtfyAdapter()
        .set_topic(config.load("ntfy.server_topic", str))
        .set_title(f"Uncaught exception on {socket.gethostname()}")
        .set_priority(config.load("ntfy.uncaught_priority", int))  # type: ignore
        .set_message(trace_str)
        .set_tags("warning", "exclamation")
        .dispatch()
    )


if __name__ == "__main__":
    sys.excepthook = exception_hook
    sys.exit(main())
