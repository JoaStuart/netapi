import os
import time
import ctypes
import asyncio
import logging
import mimetypes
import pyperclip
import api.meross
import numpy as np
import api.moisture
from time import sleep
import soundfile as sf
from api.insyde import *
import sounddevice as sd
from plyer import notification
from api.govee import GOVEE_DEVICE
from api.open_meteo import OpenMeteo
import configuration.config as cfg
from utils import img_b64, imgread_uri, tuple_lt
from webserver.webrequest import WebRequest
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)

log = logging.getLogger()


class APIRequest(WebRequest):
    DATA_RAW = "raw"
    TYPE_RAW = "raw_type"

    def REQUEST(self, path: str, body: dict) -> tuple[dict, str]:
        success = []
        send_dict = {}
        parts = path.split("/")

        for i in range(1, len(parts)):
            try:
                get_args = parts[i].lower().split(".")
                try:
                    func = getattr(self, f"API_{get_args[0]}")
                except Exception:
                    success.append(False)
                    continue

                retval = func(get_args[1:], body)
                if type(retval) != dict:
                    success.append(False)
                    continue

                send_dict |= retval
                success.append(True)
            except Exception as e:
                log.exception("Exception while APIRequest")
                success.append(False)

        if not success:
            return (
                {"message": "No API function specified!"},
                "application/json",
                (404, "NOT_FOUND"),
            )
        for i in range(len(success)):
            if success[i] == False:
                return (
                    {"message": f"API function `{parts[i + 1]}` failed!"} | send_dict,
                    "application/json",
                    (400, "FUNC_FAILED"),
                )

        if "message" not in send_dict:
            send_dict["message"] = "Done"

        if self.DATA_RAW in send_dict:
            return (
                send_dict[self.DATA_RAW],
                send_dict.get(self.TYPE_RAW, "plain/text"),
                (200, "OK"),
            )
        else:
            return send_dict, "application/json", (200, "OK")

    def play_sound(self, path: str) -> None:
        data, samplerate = sf.read(path)

        idx = -1
        dct = sd.query_devices()
        for k in dct:
            if k.get("name", "").startswith("LC34G55T"):
                idx = k.get("index", -1)
                break
        if idx >= 0:
            stream = sd.Stream(samplerate=samplerate, device=(0, 9))
        else:
            stream = sd.Stream(samplerate=samplerate)
            data /= 2
        stream.start()
        stream.write(data.astype(np.float32))
        stream.stop()

    def API_lock(self, args, body):
        ctypes.windll.user32.LockWorkStation()
        return {}

    def API_paste(self, args, body):
        return {"paste": pyperclip.paste()}

    def API_copy(self, args, body):
        if "copy" in body:
            pyperclip.copy(body["copy"])
            return {}
        return None

    def API_notify(self, args, body):
        notification.notify(
            title=body.get("title", "Notification"),
            message=body.get("message", "You got a notification!"),
            app_name="WinAPI",
            timeout=10,
        )
        return {}

    def API_play(self, args, body):
        if len(args) > 0 and os.path.isfile(f"./resources/sounds/{args[0]}.wav"):
            self.play_sound(
                f"./resources/sounds/{args[0]}.wav",
            )
            return {}
        return None

    def API_media(self, args, body):
        if len(args) == 1:

            async def control(cs: str):
                sessions = await MediaManager.request_async()
                current_session = sessions.get_current_session()
                if current_session:
                    match cs:
                        case "pause":
                            current_session.try_pause_async()
                        case "play":
                            current_session.try_play_async()
                        case "next":
                            current_session.try_skip_next_async()
                        case "prev":
                            current_session.try_skip_previous_async()
                        case "stop":
                            current_session.try_stop_async()
                        case _:
                            return False
                    return True

            return {} if asyncio.run(control(args[0])) else None

        async def get_media_info():
            sessions = await MediaManager.request_async()

            current_session = sessions.get_current_session()
            if current_session:
                info = await current_session.try_get_media_properties_async()
                info_dict = {
                    "title": info.title,
                    "artist": info.artist,
                }

                return {"media": info_dict}
            return {"media": "No media playing"}

        return asyncio.run(get_media_info())

    def API_govee(self, args, body):
        if len(args) == 0:
            return None

        match args[0]:
            case "on":
                GOVEE_DEVICE.power(True)
            case "off":
                GOVEE_DEVICE.power(False)
            case "bright":
                if len(args) == 2:
                    try:
                        GOVEE_DEVICE.brightness(int(args[1]))
                    except ValueError:
                        return None
            case _:
                return None
        return {}

    def API_wait(self, args, body):
        sleep(5)
        return {}

    def API_pwrmode(self, args, body):
        if len(args) == 0:
            return {"pwrmode": get_power_mode()}

        try:
            pwrmode = int(args[0])
            if pwrmode < 0 or pwrmode > 3:
                raise ValueError()

            set_power_mode(pwrmode)
            return {}
        except ValueError:
            return None

    def API_exit(self, args, body):
        os._exit(0)

    def API_file(self, args, body):
        contpe = self._recv_headers.get("Content-Type", None)
        if contpe == None:
            return None

        ext = mimetypes.guess_extension(contpe)
        if ext == None:
            return None

        with open(
            os.path.join(os.environ["userprofile"], f"Downloads\\{time.time()}{ext}"),
            "wb",
        ) as of:
            of.write(body)

        return {}

    def API_ext(self, args, body):
        with open(
            "C:\\Users\\Joa\\Documents\\Python\\winapi\\html\\ext.html", "rb"
        ) as rf:
            return {self.DATA_RAW: rf.read(), self.TYPE_RAW: "text/html"}

    def API_meross(self, args, body):
        if len(args) == 2:
            try:
                ch_idx = int(args[1])
            except ValueError:
                return None

            match args[0]:
                case "off":
                    api.meross.off(ch_idx)
                case "on":
                    api.meross.on(ch_idx)
                case _:
                    return None
            return {}

    def API_plants(self, args, body):
        try:
            pidx = -1 if len(args) == 0 else int(args[0])
        except:
            return None
        
        if pidx > 1:
            pidx = -1
        dta = api.moisture.read()
        crit: tuple[float, float] = tuple(cfg.read_property("plants.critical"))
        
        if pidx == -1:
            pok = tuple_lt(crit, dta)

            return {
                "streamdeck": {
                    "image": imgread_uri(f"./resources/images/plant_{"green" if pok else "red"}.png"),
                    "title": " | ".join(map(lambda f: str(round(f * 100)), dta)),
                },
                "plants": {
                    "data": list(dta),
                    "status": "OK" if pok else "NOT OK",
                },
            }
        elif pidx == 0:
            pok = crit[0] < dta[0]
            return {
                "streamdeck": {
                    "image": imgread_uri(f"./resources/images/plant_{"green" if pok else "red"}.png"),
                    "title": str(round(dta[0] * 100)),
                }
            }
        elif pidx == 1:
            pok = crit[1] < dta[1]
            return {
                "streamdeck": {
                    "image": imgread_uri(f"./resources/images/plant_{"green" if pok else "red"}.png"),
                    "title": str(round(dta[1] * 100)),
                }
            }

    def API_remote(self, args, body):
        with open(
            "C:\\Users\\Joa\\Documents\\Python\\winapi\\html\\remote.html", "rb"
        ) as rf:
            return {self.DATA_RAW: rf.read(), self.TYPE_RAW: "text/html"}
    
    def API_wttr(self, args, body):
        m = OpenMeteo()
        m.poll()
        
        return {
            "streamdeck": {
                "image": img_b64(m.sd_ico()),
                "title": f"{int(m.get("temperature_2m"))}°C",
            }
        } | m.current
    
    
    def API_mama(self, args, body):
        col = cfg.read_property("mama.status")
        note = cfg.read_property("mama.note")
        match col:
            case 0: # Alles gut
                col = "#00FF00"
            case 1: # Scheiße aber geht
                col = "#9900FF"
            case 2:
                col = "#FF0000"
            case _:
                col = "#000000"
        
        with open("./html/mama.html", "rb") as rf:
            return {
                self.DATA_RAW: rf.read().replace(b"%%STATUS%%", col.encode()).replace(b"%%NOTE%%", note.encode()),
                self.TYPE_RAW: "text/html",
            }
