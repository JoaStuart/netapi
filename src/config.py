import json
import logging
import os
from typing import Any
import locations


LOG = logging.getLogger()


def _load_json() -> dict[str, Any]:
    """Loads the JSON contents of the config file

    Returns:
        dict[str, Any]: The contents of the config file parsed into a dict
    """
    
    with open(os.path.join(locations.ROOT, "config.json"), "r") as rf:
        data = rf.read()
    return json.loads(data)


def load_envvars() -> None:
    """Loads all specified EnvVars from the config file"""

    vs = _load_var("environ")

    # Load from secrets file
    if isinstance(vs, str):
        with open(os.path.join(locations.ROOT, vs), "r") as rf:
            vs = json.loads(rf.read())

    if not isinstance(vs, dict):
        return

    for k, i in vs.items():
        os.environ[k] = i


def _load_var(path: str) -> Any | None:
    """Loads the variable located at the `path`

    Args:
        path (str): The path of the variable to load

    Returns:
        Any | None: The variable located at the `path` or none if the path is invalid
        
    Note:
        Deprecated for external use! Look at config.load_<type>(path)
    """

    try:
        data = _load_json()

        for p in path.split("."):
            data = data[p]
    except Exception:
        LOG.exception("Exception loading `%s` from config", path)
        return None

    return data

def load_str(path: str) -> str:
    """Type-testing config variable loader

    Args:
        path (str): The path of the variable to load

    Returns:
        str: The value of the variable
    """
    
    var = _load_var(path)
    if not isinstance(var, str):
        return str(var)
    return var

def load_num(path: str) -> float:
    """Type-testing config variable loader

    Args:
        path (str): The path of the variable to load

    Returns:
        float: The value of the variable
    """
    
    var = _load_var(path)
    
    if isinstance(var, float):
        return var
    
    if isinstance(var, str) or isinstance(var, int):
        return float(var)

    raise ValueError(f"No float found at {path}")

def load_int(path: str) -> int:
    """Type-testing config variable loader

    Args:
        path (str): The path of the variable to load

    Returns:
        int: The value of the variable
    """
    
    var = _load_var(path)
    
    if isinstance(var, int):
        return var
    
    if isinstance(var, str) or isinstance(var, float):
        return int(var)
    
    raise ValueError(f"No int found at {path}")

def load_dict(path: str) -> dict[str, Any]:
    """Type-testing config variable loader

    Args:
        path (str): The path of the variable to load

    Returns:
        dict[str, Any]: The value of the variable
    """
    
    var = _load_var(path)
    
    if not isinstance(var, dict):
        raise ValueError(f"No dict found at {path}")
    return var

def load_list(path: str) -> list[Any]:
    """Type-testing config variable loader

    Args:
        path (str): The path of the variable to load

    Returns:
        list[Any]: The value of the variable
    """
    
    var = _load_var(path)
    
    if not isinstance(var, list):
        raise ValueError(f"No list found at {path}")
    return var

def load_bool(path: str) -> bool:
    """Type-testing config variable loader

    Args:
        path (str): The path of the variable to load

    Returns:
        bool: The value of the variable
    """
    
    var = _load_var(path)
    
    if not isinstance(var, bool):
        return var is not None
    
    return var


def set_var(path: str, value: Any) -> None:
    """Sets the variable at `path` to the specified value

    Args:
        path (str): The path of the value
        value (Any): The value to set
    """

    data = _load_json()

    data_part = data
    path_part = path.split(".")

    for k in range(len(path_part) - 1):
        data_part = data_part[path_part[k]]

    data_part[path_part[-1]] = value

    cpath = os.path.join(locations.ROOT, "config.json")
    with open(cpath, "w") as wf:
        wf.write(json.dumps(data, indent=2))


def load_full() -> dict[str, Any]:
    """Loads the whole config file

    Returns:
        dict[str, Any]: The root node of the config file
    """

    return _load_json()
