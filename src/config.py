import json
import logging
import os
import time
from typing import Any, Type, TypeVar, Union
import locations
from proj_types.singleton import singleton


LOG = logging.getLogger()

_CAST = TypeVar("_CAST")


@singleton
class Config:
    PATH = os.path.join(locations.ROOT, "config.json")

    def __init__(self) -> None:
        self._data = self._load_config()
        self._load_time = time.time()

    def _load_config(self) -> dict[str, Any]:
        """Loads the JSON contents of the config file

        Returns:
            dict[str, Any]: The root node of the config file
        """

        with open(self.PATH, "r") as rf:
            data = rf.read()

        return json.loads(data)

    def load_envvars(self) -> None:
        """Loads all specified EnvVars from the config file"""

        self._refresh()

        vs = self.load("environ", str, dict)

        # Load from secrets file
        if isinstance(vs, str):
            with open(os.path.join(locations.ROOT, vs), "r") as rf:
                vs = json.loads(rf.read())

        if not isinstance(vs, dict):
            return

        for k, i in vs.items():
            os.environ[k] = i

    def _refresh(self) -> None:
        if os.path.getmtime(self.PATH) > self._load_time:
            self._data = self._load_config()
            self._load_time = time.time()

    def _load_path(self, path: str) -> Any:
        """Loads the variable located at the `path`

        Args:
            path (str): The path of the variable to load

        Returns:
            Any | None: The variable located at the `path` or none if the path is invalid
        """

        self._refresh()

        data = self._data

        try:
            for p in path.split("."):
                data = data[p]
        except Exception:
            LOG.exception("Exception loading `%s` from config", path)
            return None

        return data

    def load(self, path: str, *cast: Type[_CAST]) -> _CAST:
        val = self._load_path(path)

        for c in cast:
            if isinstance(val, c):
                return val

        raise ValueError(f"None of {cast} found at {path}")

    def set(self, path: str, val: Any) -> None:
        """Sets the variable at `path` to the specified value

        Args:
            path (str): The path of the value
            val (Any): The value to set
        """

        self._refresh()

        data = self._data

        data_part = data
        path_part = path.split(".")

        for k in range(len(path_part) - 1):
            data_part = data_part[path_part[k]]

        data_part[path_part[-1]] = val

        with open(Config.PATH, "w") as wf:
            wf.write(json.dumps(data, indent=2))

    def root(self) -> dict[str, Any]:
        return self._data


Config().load_envvars()

load = Config().load
set = Config().set
root = Config().root
