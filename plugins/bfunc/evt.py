"""
Internally needed backend function!
Makes the receiving endpoint for the Event system
 
"""

import traceback
from backend.event import Event
from device.api import APIFunct
from proj_types.event_type import EventType


class Evt(APIFunct):
    def api(self) -> dict | tuple[bytes, str]:
        try:
            Event.trigger_all(EventType[self.args[0]])
            return {"evt": f"Dispatched `{self.args[0]}`"}
        except KeyError:
            return {"evt": "This event type is not registered!"}
        except Exception:
            return {
                "evt": {
                    "message": "Failed to dispatch event",
                    "traceback": traceback.format_exc(),
                }
            }

    def permissions(self, default: int) -> int:
        return 100
