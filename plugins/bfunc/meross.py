import asyncio
import os
from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager

from device.api import APIFunct, APIResult


class Meross(APIFunct):
    def api(self) -> APIResult:
        if len(self.args) != 2:
            return APIResult.by_msg(
                "Usage: `/meross.<on/off>.<channel>` or `/meross.<on/off>.<device>.<channel>`",
                success=False,
            )

        try:
            device = 0 if len(self.args) == 2 else int(self.args[1])
            channel = int(self.args[1]) if len(self.args) == 2 else int(self.args[2])

            return asyncio.run(self.aapi(device, channel))
        except Exception:
            return APIResult.by_msg("Argument 2 must be a channel!", success=False)

    async def aapi(self, device: int, channel: int) -> APIResult:
        client = await MerossHttpClient.async_from_user_password(
            api_base_url="https://iotx-eu.meross.com",
            email=os.environ["MEROSS_MAIL"],
            password=os.environ["MEROSS_PASS"],
        )

        manager = MerossManager(http_client=client)
        await manager.async_device_discovery()

        devices = manager.find_devices()
        if len(devices) < 1:
            return APIResult.by_msg("No devices found", success=False)

        dev = devices[device]

        if self.args[0] == "on":
            await dev.async_turn_on(channel=channel)
        elif self.args[0] == "off":
            await dev.async_turn_off(channel=channel)
        else:
            return APIResult.by_msg("Argument 1 must be on/off", success=False)

        manager.close()
        await client.async_logout()

        return APIResult.by_success(True)