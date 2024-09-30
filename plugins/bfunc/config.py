import config
from device.api import APIFunct


class Config(APIFunct):
    def api(self) -> dict | tuple[bytes, str]:
        if len(self.args) == 0:
            return config.load_full()

        elif "config" not in self.body:
            return {"message": "Argument and body needed"}
        else:
            if self.args[0] == "set":
                c = self.body["config"]
                for k, v in c.items():
                    config.set_var(k, v)
                return {"message": "Config value set"}
        return {"message": f"Argument {self.args[0]} not recognized!"}
