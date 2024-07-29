import os
import sys
import time
import logging
import argparse
from backend.backend import BackendRequest
from config import load_envvars
from locations import ROOT
from webserver.webserver import WebServer


LOG = logging.getLogger()


def setup_logger(verbose: bool) -> None:
    logFormatter = logging.Formatter(
        "%(asctime)s :: >%(threadName)-12.12s< [%(levelname)-1.1s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    LOG.setLevel(logging.DEBUG)

    logPath = os.path.join(ROOT, "logs")
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

    LOG.info("Starting...")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "devtype",
        choices=["frontend", "backend"],
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

    if args.devtype == "frontend":
        # start frontend
        pass
    else:
        # start backend
        srv = WebServer(4001, BackendRequest)
        srv.start_blocking()
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
