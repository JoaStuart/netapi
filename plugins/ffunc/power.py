import subprocess
from device.api import APIFunct, APIResult


class Power(APIFunct):
    """Initiates a power action on the current windows device"""

    def api(self) -> APIResult:

        if len(self.args) == 0:
            return APIResult.by_msg("Modes supported: [off]", success=False)
        elif self.args[0] == "off":
            subprocess.run(["shutdown", "-s", "-t", "0"])

        return APIResult.by_success(True)
