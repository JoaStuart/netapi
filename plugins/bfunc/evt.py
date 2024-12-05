"""
Internally needed backend function!
Makes the receiving endpoint for the Event system
 
"""

import traceback
from backend.event import Event
from device.api import APIFunct, APIResult
from proj_types.event_type import EventType


class Evt(APIFunct):
    def api(self) -> APIResult:
        try:
            Event.trigger_all(EventType[self.args[0]])
            return APIResult.by_msg(f"Dispatched `{self.args[0]}`")
        except KeyError:
            return APIResult.by_msg("This event type is not registered!", success=True)
        except Exception:
            return APIResult.by_json(
                {
                    "message": "Failed to dispatch event",
                    "traceback": traceback.format_exc(),
                },
                success=False,
            )

    def permissions(self, default: int) -> int:
        return 100
