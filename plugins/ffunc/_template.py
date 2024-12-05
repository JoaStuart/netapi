from device.api import APIFunct, APIResult


class TemplateFunc(APIFunct):
    def api(self) -> APIResult:
        # Do stuff

        return APIResult.by_msg("Hello world!")
