from device.api import APIFunct


class TemplateFunc(APIFunct):
    def api(self) -> dict | tuple[bytes, str]:
        # Do stuff

        return {"message": "Hello world!"}
