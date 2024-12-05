import cv2
import mss
import webbrowser
import numpy as np
import tkinter as tk
import pyperclip
import pyzbar.pyzbar
from threading import Thread
from tkinter import messagebox

from device.api import APIFunct, APIResult


class ScreenQR(APIFunct):
    def api(self) -> APIResult:
        code_list: list[str] = []

        with mss.mss() as sct:
            monitors = sct.monitors

            for _, monitor in enumerate(monitors[1:], start=1):
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                codes = pyzbar.pyzbar.decode(img)

                for qr_code in codes:
                    data = qr_code.data.decode("utf-8", errors="ignore")
                    code_list.append(data)

        if len(self.args) > 0 and self.args[0] == "prompt":
            Thread(target=self.ask_all_links, args=(code_list,)).start()

        return APIResult.by_json(code_list)

    def ask_all_links(self, code_list: list[str]):
        if len(code_list) == 0:
            return

        root = tk.Tk()
        root.attributes("-topmost", True)
        # root.update()
        root.withdraw()

        for data in code_list:
            is_link = data.startswith("http")
            msg = (
                "Do you want to open this link?"
                if is_link
                else "Do you want to copy the QR data to your clipboard?"
            )

            if messagebox.askyesno("QRCode", f"{msg}\n{data}", parent=root):
                if is_link:
                    webbrowser.open(data)
                else:
                    pyperclip.copy(data)

        root.destroy()
