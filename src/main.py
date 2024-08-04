import os
import sys
import time
import logging
import argparse
import zipfile
from backend.backend import BackendRequest
from config import load_envvars
import config
from device.device import DEV_PORT, FrontendDevice
from frontend.frontend import FrontendRequest
import locations
from webserver.webserver import WebServer


LOG = logging.getLogger()
VERSION = 0.1


def setup_logger(verbose: bool) -> None:
    logFormatter = logging.Formatter(
        "%(asctime)s :: >%(threadName)-12.12s< [%(levelname)-1.1s] %(message)s",
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


def main() -> int:
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
    args = p.parse_args()

    setup_logger(args.verbose)
    load_envvars()

    for k in os.listdir(locations.ROOT):
        name, ext = os.path.splitext(k)
        if not name.startswith("netapi-"):
            continue

        v = float(name.split("-")[1])
        if v > VERSION:
            LOG.info(f"Updating netapi to version {v}...")
            locations.unpack(os.path.join(locations.ROOT, k))
            os.remove(os.path.join(locations.ROOT, k))
            return 12  # Restart script

    locations.make_dirs()

    match args.action:
        case "frontend":
            LOG.info("Starting [FRONTEND]...")
            # Log in and start frontend
            try:
                fdev = FrontendDevice()
                fdev.login()
            except Exception:
                LOG.warning(f"Login failed at {config.load_var("backend")}. Exiting...")
                return 1

            srv = WebServer(DEV_PORT, FrontendRequest)
            srv.start_blocking()
        case "backend":
            LOG.info("Starting [BACKEND]...")
            # start backend
            srv = WebServer(DEV_PORT, BackendRequest)
            srv.start_blocking()
        case "pack":
            LOG.info("Packing source...")
            # Pack source files
            zname = f"{locations.ROOT}/netapi-{VERSION}.zip"
            locations.compress_pkg(zname)

    return 0


if __name__ == "__main__":
    sys.exit(main())
