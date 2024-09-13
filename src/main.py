import os
import sys
import time
import logging
import argparse
import signal
from typing import NoReturn
from device.device import DEV_PORT
from config import load_envvars
import config
import locations
from utils import CleanUp
from webserver.webserver import WebServer


LOG = logging.getLogger(__name__)
VERSION = 0.2
CLEANUP_STACK: list[CleanUp] = []


def handle_cleanup(*args, **kwargs) -> NoReturn:
    """Handle the cleanup upon any revieced signal"""

    for c in CLEANUP_STACK:
        c.cleanup()
    CLEANUP_STACK.clear()
    exit(0)


for sig in [signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, handle_cleanup)


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
    os.execl(sys.executable, __file__, *sys.argv[1:])


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


def main() -> int:
    args = parse_args()

    setup_logger(args.verbose)
    load_envvars()

    update()

    locations.make_dirs()

    pack("/public/pack.zip")

    act = args.action

    if act == "frontend":
        from frontend.systray import SysTray
        from device.device import FrontendDevice
        from frontend.frontend import FrontendRequest

        LOG.info("Starting [FRONTEND]...")
        tray = SysTray()
        CLEANUP_STACK.append(tray)
        tray.start()
        # Log in and start frontend
        try:
            fdev = FrontendDevice()
            CLEANUP_STACK.append(fdev)
            fdev.login(VERSION)
        except Exception:
            tray.update_icon(SysTray.FAILED)
            LOG.warning(f"Login failed at {config.load_var("backend")}. Exiting...")
            time.sleep(2)
            CLEANUP_STACK.remove(fdev)
            return 1

        tray.update_icon(SysTray.CONNECTED)
        srv = WebServer(DEV_PORT, FrontendRequest)
        CLEANUP_STACK.append(srv)
        srv.start_blocking()
    elif act == "backend":
        from backend.backend import DEVICES, BackendRequest

        LOG.info("Starting [BACKEND]...")
        # start backend
        srv = WebServer(DEV_PORT, BackendRequest)
        CLEANUP_STACK.append(srv)

        class BC(CleanUp):
            def cleanup(self) -> None:
                for _, d in DEVICES.items():
                    d.close()

        CLEANUP_STACK.append(BC())

        srv.start_blocking()
        handle_cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
