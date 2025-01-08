import requests
import config
from device.api import APIFunct, APIResult
from device.ntfy import NtfyAdapter


class Ntfy(APIFunct):
    def api(self) -> APIResult:
        NtfyAdapter().read_json(self.body).dispatch()

        return APIResult.by_msg("Notification sent!")
