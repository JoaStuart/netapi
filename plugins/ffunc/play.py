import os
import numpy as np
import soundfile as sf
import sounddevice as sd
from device.api import APIFunct, APIResult

import config
import locations


class Play(APIFunct):
    """Play Function for JoaLaptop specific device"""

    def api(self) -> APIResult:
        if len(self.args) >= 1:
            sound = os.path.join(
                locations.ROOT, "resources", "sounds", f"{self.args[0]}.wav"
            )

            if os.path.isfile(sound):
                data, samplerate = sf.read(sound)

                idx = -1
                dct = sd.query_devices()
                for k in dct:
                    if not isinstance(k, dict):
                        continue

                    if k.get("name", "").startswith(config.load_var("play.outdevice")):
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
                return APIResult.by_success(True)
            else:
                return APIResult.by_msg(
                    "Specified song not found, aborting.", success=False
                )

        else:
            return APIResult.by_msg("No sound specified, aborting.", success=False)
