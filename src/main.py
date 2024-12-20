import os
import sys
import time
import logging
import argparse
import signal
from typing import NoReturn
from backend.automation import Automation
from backend.interval import Schedule
from backend.multicast_srv import MulticastServer
from device.device import DEV_PORT
from config import load_envvars
from frontend.multicast_cli import MulticastClient
from locations import VERSION
import config
import locations
from log import append_http_logger, init_logger
from utils import CleanUp
from webserver.webserver import WebServer

from log import LOG

CLEANUP_STACK: list[CleanUp] = []


def handle_cleanup(*args, **kwargs) -> NoReturn:
    """Handle the cleanup upon any revieced signal"""

    LOG.info("Starting cleanup")

    for c in CLEANUP_STACK:
        c.cleanup()
    CLEANUP_STACK.clear()
    exit(0)


for sig in [signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, handle_cleanup)


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
    from frontend.systray import SysTray
    from device.device import FrontendDevice
    from frontend.frontend import FrontendRequest

    LOG.info("Starting [FRONTEND]...")

    # Start systray
    tray = SysTray()
    CLEANUP_STACK.append(tray)
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
        CLEANUP_STACK.append(fdev)
        fdev.login(VERSION)
    except Exception:
        tray.update_icon(SysTray.FAILED)
        LOG.exception(f"Login failed at {ip}. Exiting...")
        time.sleep(2)
        CLEANUP_STACK.remove(fdev)
        return 1

    append_http_logger(ip, DEV_PORT, fdev)

    tray.update_icon(SysTray.CONNECTED)
    tray.handle_cleanup = handle_cleanup

    LOG.info("Connected to backend")
    srv = WebServer(DEV_PORT, FrontendRequest, {"ip": ip})
    CLEANUP_STACK.append(srv)
    srv.start_blocking()


def backend() -> None | int:
    from backend.backend import DEVICES, BackendRequest

    LOG.info("Starting [BACKEND]...")
    # Start Multicast backend
    multi_server = MulticastServer()
    multi_server.background_listen()

    # start backend
    srv = WebServer(DEV_PORT, BackendRequest)
    CLEANUP_STACK.append(srv)

    class BC(CleanUp):
        def cleanup(self) -> None:
            for _, d in DEVICES.items():
                d.close()

    CLEANUP_STACK.append(BC())

    Schedule.start_scheduler()
    LOG.info("Started scheduler")

    Automation.load_all()
    LOG.info("Loaded automations")

    srv.start_blocking()
    handle_cleanup()


def main() -> int:
    args = parse_args()

    init_logger(args.verbose)
    load_envvars()

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


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        LOG.exception("Caught exception at project root:")
        sys.exit(1)
