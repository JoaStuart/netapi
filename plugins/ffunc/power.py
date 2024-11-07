import subprocess
from device.api import APIFunct


class Power(APIFunct):
    """Initiates a power action on the current windows device"""

    def api(self) -> dict | tuple[bytes, str]:

        if len(self.args) == 0:
            return {"power": "Modes supported: [off]"}
        elif self.args[0] == "off":
            subprocess.run(["shutdown", "-s", "-t", "0"])

        return {}
