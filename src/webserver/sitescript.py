from abc import ABC, abstractmethod
import importlib
import importlib.util
import logging
import os
import traceback
from typing import Any, Type


from log import LOG


class SiteScript(ABC):
    def __init__(self, getargs: dict[str, Any]) -> None:
        self.page_vars: dict[str, str | bytes] = {}
        self.get_args = getargs
        self.headers = {}

    @abstractmethod
    def display(self) -> None:
        """Perform site manipulation"""

        pass

    def site_read(self, sitefile: str) -> bytes:
        """Reads the site from the provided sitefile

        Args:
            sitefile (str): The path to the file to be read

        Returns:
            bytes: The contents of the file, manipulated by the SiteScript
        """

        self.display()

        with open(sitefile, "rb") as rf:
            content = rf.read()

        for k, v in self.page_vars.items():
            content = content.replace(
                f"%%{k}%%".encode(), v.encode() if isinstance(v, str) else v
            )

        return content


def load_script_file(pldir: str, f: str) -> Type[SiteScript] | None:
    """Loads the SiteScript file located at `pldir/f`

    Args:
        pldir (str): The directory the file is located in
        f (str): The file name

    Returns:
        Type[SiteScript] | None: The SiteScript if one is found, else None
    """

    plugin_path = os.path.join(pldir, f)
    module_name = f[:-3]

    try:
        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        if spec == None:
            return None
        module = importlib.util.module_from_spec(spec)
        loader = spec.loader
        if loader == None:
            return None
        loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, SiteScript)
                and attr is not SiteScript
            ):
                return attr

    except Exception:
        LOG.exception("Plugin %s did not load successfully:", f)
        traceback.print_exc()
