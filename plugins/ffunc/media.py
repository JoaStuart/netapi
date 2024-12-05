import asyncio
from device.api import APIFunct, APIResult
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)


class Media(APIFunct):
    """Windows specific media session lookup and control."""

    def api(self) -> APIResult:
        if len(self.args) == 1:

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

            return (
                APIResult.by_success(True)
                if asyncio.run(control(self.args[0]))
                else APIResult.by_msg(f"Function {self.args[0]} failed.", success=False)
            )

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

        return APIResult.by_json(asyncio.run(get_media_info()))
