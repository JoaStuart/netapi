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
