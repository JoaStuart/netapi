from abc import ABC, abstractmethod
import importlib
import logging
import os
import traceback
from typing import Type


LOG = logging.getLogger()


class SiteScript(ABC):
    def __init__(self) -> None:
        self.page_vars: dict[str, str] = {}

    @abstractmethod
    def display(self) -> None:
        """Perform site manipulation"""
        pass

    def site_read(self, sitefile: str) -> bytes:
        with open(sitefile, "rb") as rf:
            content = rf.read()

        self.display()

        for k, v in self.page_vars.items():
            content = content.replace(f"%%{k}%%".encode(), v.encode())

        return content


def load_script_file(pldir: str, f: str) -> Type[SiteScript] | None:
    plugin_path = os.path.join(pldir, f)
    module_name = f[:-3]

    try:
        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

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
