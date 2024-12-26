import config
from device.api import APIFunct, APIResult


class Config(APIFunct):
    def api(self) -> APIResult:
        if len(self.args) == 0:
            return APIResult.by_json(config.root())

        elif "config" not in self.body:
            return APIResult.by_msg("Argument and body needed", success=False)
        else:
            if self.args[0] == "set":
                c = self.body["config"]
                for k, v in c.items():
                    config.set(k, v)
                return APIResult.by_msg("Config value set")
        return APIResult.by_msg(
            f"Argument {self.args[0]} not recognized!", success=False
        )
