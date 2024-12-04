import json
import logging
import os
from typing import Any
from locations import ROOT
import locations


LOG = logging.getLogger()


def __load_json(path: str) -> dict:
    with open(os.path.join(ROOT, "config.json"), "r") as rf:
        return json.loads(rf.read())


def load_envvars() -> None:
    """Loads all specified EnvVars from the config file"""

    vs = load_var("environ")

    # Load from secrets file
    if isinstance(vs, str):
        with open(os.path.join(locations.ROOT, vs), "r") as rf:
            vs = json.loads(rf.read())

    if not isinstance(vs, dict):
        return

    for k, i in vs.items():
        os.environ[k] = i


def load_var(path: str) -> Any | None:
    """Loads the variable located at the `path`

    Args:
        path (str): The path of the variable to load

    Returns:
        Any | None: The variable located at the `path` or none if the path is invalid
    """

    try:
        data = __load_json(os.path.join(ROOT, "config.json"))

        for p in path.split("."):
            data = data[p]
    except Exception:
        LOG.exception("Exception loading `%s` from config", path)
        return None

    return data


def set_var(path: str, value: Any) -> None:
    """Sets the variable at `path` to the specified value

    Args:
        path (str): The path of the value
        value (Any): The value to set

    APINote:
        Still untested because I dont fucking know what this will result in ._.
    """

    cpath = os.path.join(ROOT, "config.json")
    data = __load_json(cpath)

    data_part = data
    path_part = path.split(".")

    for k in range(len(path_part) - 1):
        data_part = data_part[path_part[k]]

    data_part[path_part[-1]] = value

    with open(cpath, "w") as wf:
        wf.write(json.dumps(data, indent=2))


def load_full() -> dict:
    """Loads the whole config file

    Returns:
        dict[Any, Any]: The root node of the config file
    """

    return __load_json(os.path.join(ROOT, "config.json"))
