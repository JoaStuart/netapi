import logging
import os
from threading import Thread
import tkinter as tk
from tkinter import simpledialog
from typing import NoReturn, Callable
import pystray
from PIL import Image

from device.device import FrontendDevice
import locations
from proj_types.singleton import singleton
from proj_types.cleanup import CleanUp

LOG = logging.getLogger()


class TrayState:
    CONNECTING = 0
    CONNECTED = 1
    FAILED = 2


@singleton
class SysTray(CleanUp):

    def __init__(self) -> None:
        self._icon = None
        self.handle_cleanup: Callable[..., NoReturn] | None = None
        self._entries: list[pystray.MenuItem] = [
            pystray.MenuItem("APIRequest", self._create_request),
            pystray.MenuItem("Exit", self.cleanup),
        ]

        self._tray = pystray.Icon(
            NAME := "NetAPI",
            self._icon_by_state(TrayState.CONNECTING),
            NAME,
            self._entries,
        )

    def _create_request(self) -> None:
        root = tk.Tk()
        root.withdraw()
        path = simpledialog.askstring("API Request", "Request path:")
        if path is None:
            return

        FrontendDevice("")._action_client(path).send()

    def start(self) -> None:
        Thread(target=self._tray.run, daemon=True).start()

    def _load_icon(self):
        self._icon = Image.open(os.path.join(locations.PUBLIC, "favicon.ico"))

    def _icon_by_state(self, state: int):
        if self._icon == None:
            self._load_icon()

        match state:
            case TrayState.CONNECTING:
                return replace_color(self._icon, (0xE8, 0xEA, 0xED), (0xFF, 0xFF, 0x00))  # type: ignore
            case TrayState.CONNECTED:
                return replace_color(self._icon, (0xE8, 0xEA, 0xED), (0x00, 0xFF, 0x00))  # type: ignore
            case TrayState.FAILED:
                return replace_color(self._icon, (0xE8, 0xEA, 0xED), (0xFF, 0x00, 0x00))  # type: ignore

        return self._icon

    def update_icon(self, state: int) -> None:
        self._tray.icon = self._icon_by_state(state)
        self._tray._update_icon()

    def _update_menu(self) -> None:
        self._tray.menu = self._entries
        self._tray.update_menu()

    def cleanup(self) -> None:
        if not self._tray._running:
            return

        self._tray.visible = False
        self._tray.stop()

        if self._icon != None:
            self._icon.close()

        if self.handle_cleanup != None:
            self.handle_cleanup()

    def add_entry(self, entry: pystray.MenuItem) -> None:
        LOG.info(f"Added {entry.text}")
        self._entries.append(entry)
        self._update_menu()


def replace_color(
    image: Image.Image, target_color: tuple, replacement_color: tuple
) -> Image.Image:
    """
    Replace a specific color in a PIL Image with another color.

    Parameters:
        image (Image.Image): The input PIL Image.
        target_color (tuple): The RGB color to replace (R, G, B).
        replacement_color (tuple): The RGB color to use as a replacement (R, G, B).

    Returns:
        Image.Image: The modified PIL Image with the specified color replaced.
    """
    # Convert the image to RGB if it is not already in that mode
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Create a new image to store the modified pixels
    new_image = Image.new("RGB", image.size)

    # Load pixel data
    pixels = image.load()
    new_pixels = new_image.load()

    if pixels == None or new_pixels == None:
        raise Exception("Image pixels could not be loaded!")

    # Iterate over all pixels in the image
    for y in range(image.height):
        for x in range(image.width):
            current_color = pixels[x, y]
            # Replace the target color with the replacement color
            if current_color == target_color:
                new_pixels[x, y] = replacement_color
            else:
                new_pixels[x, y] = current_color

    return new_image
