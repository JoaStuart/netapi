import json
import logging
import os
from typing import Any
from locations import ROOT


LOG = logging.getLogger()


def load_envvars() -> None:
    vs = load_var("environ")
    if not isinstance(vs, dict):
        return

    for k, i in vs.items():
        os.environ[k] = i


def load_var(path: str) -> Any | None:
    try:
        with open(os.path.join(ROOT, "config.json"), "r") as rf:
            data = json.loads(rf.read())

        for p in path.split("."):
            data = data[p]
    except Exception:
        LOG.exception("Exception loading variable from config")
        return None

    return data


def set_var(path: str, value: Any) -> None:
    cp = os.path.join(ROOT, "config.json")

    with open(cp, "r") as rf:
        data = json.loads(rf.read())

    data_part = data
    path_part = path.split(".")
    for k in range(len(path_part) - 1):
        data_part = data_part[path_part[k]]

    data_part[path_part[-1]] = value

    with open(cp, "w") as wf:
        wf.write(json.dumps(data, indent=2))
