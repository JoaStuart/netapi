import importlib
import importlib.util
import os
import logging
import traceback
from typing import Type

LOG = logging.getLogger()


def load_plugins(pldir: str, pl_type: list[Type]) -> dict[Type, dict[str, Type]]:
    """Loads all plugins located inside the provided directory

    Args:
        pldir (str): Parent directory of the plugins
        pl_type (list[Type]): The type the plugins should have

    Returns:
        dict[Type, dict[str, Type]]: All loaded plugins
    """

    pl = {t: {} for t in pl_type}

    for f in os.listdir(pldir):
        if f.endswith(".py") and not f.startswith("_"):
            plugin_path = os.path.join(pldir, f)
            module_name = f[:-3]

            try:
                spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                if spec == None:
                    LOG.warning("PluginLoader Spec returned None")
                    return pl

                module = importlib.util.module_from_spec(spec)
                loader = spec.loader
                if loader == None:
                    LOG.warning("PluginLoader SpecLoader returned None")
                    return pl

                loader.exec_module(module)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    for t in pl_type:
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, t)
                            and attr is not pl_type
                        ):
                            pl[t] |= {attr_name: attr}

            except Exception:
                LOG.exception("Plugin %s did not load successfully:", f)

    return pl
