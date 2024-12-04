from datetime import datetime
from enum import Enum
import json
import logging
import os
import re
import threading
from typing import Any, cast

import locations
from proj_types.event_type import EventType


LOG = logging.getLogger()


class Event:
    _events: list["Event"] = []
    _trigger: threading.Event = threading.Event()
    _queue: list[EventType] = []

    @staticmethod
    def load_all() -> None:
        """Loads all event triggers inside the directory"""

        dir = locations.AUTOMATION

        for k in os.listdir(dir):
            if k.startswith("_"):
                continue

            with open(os.path.join(dir, k), "r") as rf:
                data = json.loads(rf.read())

            if data.get("@type", None) != "event":
                continue

            LOG.debug("Loading event %s", data.get("title", ""))

            Event.add_event(data)

        threading.Thread(
            target=Event._event_thread, daemon=True, name="EventThread"
        ).start()

    @staticmethod
    def _event_thread() -> None:
        while True:
            Event._trigger.wait()

            for et in Event._queue:
                for evt in Event._events:
                    if evt.event == et and evt.check_time():
                        evt.trigger()

            Event._queue.clear()
            Event._trigger.clear()

    @staticmethod
    def add_event(data: dict[str, Any]) -> None:
        try:
            tpe = EventType[data.get("event", "")]
            title: str = data.get("title", "No title!")
            then: list[dict[str, Any]] = data.get("then", [])

            e = Event(tpe, title, then)
            if "time" in data:
                e._set_time(data["time"])

            Event._events.append(e)

        except Exception as e:
            LOG.warning("Exception on event load:", exc_info=True)

    @staticmethod
    def trigger_all(tpe: EventType) -> None:
        Event._queue.append(tpe)
        Event._trigger.set()

    def __init__(
        self, event: EventType, title: str, then: list[dict[str, Any]]
    ) -> None:
        self._event = event
        self._title = title
        self._then = then
        self._time = None

    @property
    def event(self) -> EventType:
        return self._event

    def _set_time(self, time: str | None):
        self._time = time

    def _seconds_of_day(self, t: tuple[int, int, int]) -> int:
        """Converts HH:mm:ss into the seconds that have passed since midnight

        Args:
            t (tuple[int, int, int]): The time HH:mm:ss as a tuple

        Returns:
            int: The seconds passed since midnight
        """

        return (t[0] * 60 * 60) + (t[1] * 60) + t[2]

    def check_time(self) -> bool:
        """Checks if the time set in the event matches the time we have

        Returns:
            bool: Whether the time matches
        """

        if self._time == None:
            return True

        # Get the current time in seconds
        now = datetime.now()
        current_seconds = self._seconds_of_day((now.hour, now.minute, now.second))

        # Pattern for a time like $20:00
        timepattern = r"\$([0-1]?[0-9]|2[0-3]):([0-5][0-9])(?::[0-5][0-9])?"
        matches = re.findall(timepattern, self._time)

        timevars: dict[str, int] = {}
        for match in matches:
            match: tuple[str, str] | tuple[str, str, str] = match

            # Convert match to int, but python type checker
            # doesnt like that it might have different lengths
            tme = cast(
                tuple[int, int] | tuple[int, int, int],
                tuple(int(p) for p in match),
            )

            if len(tme) == 2:
                tme = (*tme, 0)

            timevars[f"${":".join(match)}"] = self._seconds_of_day(tme)

        # Insert the seconds since midnight into the time
        # string where they are supposed to go
        time_str = self._time.replace("$now", str(current_seconds))

        for s, t in timevars.items():
            time_str = time_str.replace(s, str(t))

        # Evaluate the time string
        return bool(eval(time_str, {}, {}))

    def trigger(self) -> None:
        for req in self._then:
            path: str = req.get("path", None)
            if path is None:
                continue

            # Execute the
            fargs = path.strip("/").split(".")

            from backend.backend import BackendRequest

            BackendRequest.execute_backend(fargs, req.get("body", {}))
