import asyncio
from device.api import APIFunct
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)


class Media(APIFunct):
    """Windows specific media session lookup and control."""

    def api(self) -> dict | tuple[bytes, str]:
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
                {}
                if asyncio.run(control(self.args[0]))
                else {"media": f"Function {self.args[0]} failed."}
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

        return asyncio.run(get_media_info())
