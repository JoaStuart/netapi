from abc import ABC, abstractmethod
import base64
import hashlib
import json
import logging
import math
import mimetypes
import os
import platform
from types import UnionType
from typing import Any, ItemsView, Iterable, Iterator, KeysView, ValuesView
import zipfile

import cv2

log = logging.getLogger()


class CaseInsensitiveDict[_T]:
    def __init__(self, data: dict[str, _T] | None = None) -> None:
        self._data = {}
        if data is not None:
            for key, value in data.items():
                self._data[key.lower()] = value

    def __setitem__(self, key: str, value: _T) -> None:
        self._data[key.lower()] = value

    def __getitem__(self, key: str) -> _T:
        return self._data[key.lower()]

    def __delitem__(self, key: str) -> None:
        del self._data[key.lower()]

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._data

    def get(self, key: str, default: _T | None = None) -> _T | None:
        return self._data.get(key.lower(), default)

    def keys(self) -> KeysView[str]:
        return self._data.keys()

    def items(self) -> ItemsView[str, _T]:
        return self._data.items()

    def values(self) -> ValuesView[_T]:
        return self._data.values()

    def __repr__(self) -> str:
        return repr(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[_T]:
        return iter(self._data)

    def dict(self) -> dict[str, _T]:
        return {k: v for k, v in self.items()}


def make_token(ip: str) -> str:
    """Generates a legacy token [Deprecated]

    Args:
        ip (str): The IP of the target

    Returns:
        str: The generated token
    """

    hip = hashlib.md5(ip.encode())
    tarr = [0xFF - i for i in hip.digest()]

    return "".join(["{:02x}".format(a) for a in tarr])


def tuple_lt(tpl_lower: tuple[float], tpl_higher: tuple[float]) -> bool:
    """Checks if the first tuple is less than (<) the second

    Args:
        tpl_lower (tuple): The tuple supposed to be lower
        tpl_higher (tuple): The tuple supposed to be higher

    Returns:
        bool: Whether the first tuple is less than (<) the second
    """

    assert len(tpl_lower) == len(tpl_higher)

    for i in range(len(tpl_lower)):
        if tpl_lower[i] >= tpl_higher[i]:
            return False
    return True


def imgread_uri(path: str) -> str:
    """Reads an image from the provided path into a b64 data url

    Args:
        path (str): The path to the image

    Returns:
        str: The image as a b64 encoded data url
    """

    img = cv2.imread(path)
    return img_b64(img)


def img_b64(img: cv2.typing.MatLike) -> str:
    """Encodes a cv2 MatLike object to a b64 data url

    Args:
        img (cv2.typing.MatLike): The image to encode

    Returns:
        str: The image as a b64 encoded data url
    """

    png = cv2.imencode(".png", img)
    b64 = base64.standard_b64encode(png[1].tobytes()).decode()
    return f"data:image/png;base64,{b64}"


def mime_by_ext(file: str) -> str:
    """Get the MIME type of a file

    Args:
        file (str): The file path

    Returns:
        str: The MIME type or `application/octet-stream` if unknown
    """

    t = mimetypes.guess_type(file)
    if t[0] == None:
        return "application/octet-stream"

    return t[0]


def dumpb(d: dict) -> tuple[bytes, str]:
    return (json.dumps(d).encode(), "application/json")


def compress_dir(
    zip: zipfile.ZipFile,
    dir: str,
    path: str = "",
    dir_excl_pref: str = "__",
    file_incl_pref: str = "",
) -> None:
    """Compresses a directory into a ZIP file

    Args:
        zip (zipfile.ZipFile): The ZIP file handle
        dir (str): The parent directory to be copied into the ZIP file
        path (str, optional): The iniial path for the zip file. Defaults to "".
        dir_excl_pref (str, optional): The exclusion parameter for directories. Defaults to "__".
        file_incl_pref (str, optional): The inclusion parameter for files. Defaults to "".
    """

    for k in os.listdir(dir):
        file = os.path.join(dir, k)
        if os.path.isfile(file) and k.startswith(file_incl_pref):
            compress_file(zip, file, f"{path}/{k}")
        elif os.path.isdir(file) and not k.startswith(dir_excl_pref):
            compress_dir(zip, file, f"{path}/{k}")


def compress_file(
    zip: zipfile.ZipFile,
    file: str,
    path: str,
) -> None:
    """Writes the file into the ZIP file

    Args:
        zip (zipfile.ZipFile): The ZIP file handle
        file (str): The path of the file to get compressed
        path (str): The path inside the ZIP file of this file
    """

    zip.write(file, path)


def get_os_name() -> str:
    """
    Returns:
        str: The full OS name
    """

    return " ".join([platform.system(), platform.release()])


def load_dict_var(dct: dict, path: str) -> Any:
    """Loads a variable from a variable depth dictionary

    Args:
        dct (dict): Dictionary to search
        path (str): Path of variable to get

    Returns:
        Any: The value of the variable
    """

    parts = path.split(".")

    for p in parts:
        dct = dct[p]

    return dct
