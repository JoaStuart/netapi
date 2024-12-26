from datetime import datetime
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
            if not k.endswith(".json") or k.startswith("_"):
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
                    if et == evt.event:
                        evt.trigger()

            Event._queue.clear()
            Event._trigger.clear()

    @staticmethod
    def add_event(data: dict[str, Any]) -> None:
        try:
            tpe = EventType[data.get("event", "")]
            title: str = data.get("title", "No title!")
            actions: list[Any] = data.get("actions", [])

            e = Event(tpe, title, actions)

            Event._events.append(e)

        except Exception as e:
            LOG.warning("Exception on event load:", exc_info=True)

    @staticmethod
    def trigger_all(tpe: EventType) -> None:
        Event._queue.append(tpe)
        Event._trigger.set()

    def __init__(
        self,
        event: EventType,
        title: str,
        actions: list[Any],
    ) -> None:
        self._event = event
        self._title = title
        self._actions = actions

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

    def _replace_time(self, data: str) -> str:
        # Get the current time in seconds
        now = datetime.now()
        current_seconds = self._seconds_of_day((now.hour, now.minute, now.second))

        # Pattern for a time like $20:00
        timepattern = r"\$([0-1]?[0-9]|2[0-3]):([0-5][0-9])(?::[0-5][0-9])?"
        matches = re.findall(timepattern, data)

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
        time_str = data.replace("$time", str(current_seconds))

        for s, t in timevars.items():
            time_str = time_str.replace(s, str(t))

        return time_str

    def _replace_date(self, data: str) -> str:
        now = datetime.now()

        day_of_year = now.month * 31 + now.day

        daypattern = r"\$([12][0-9]|3[01]|[1-9])\.(1[0-2]|[1-9])\."
        matches = re.findall(daypattern, data)

        dayvars: dict[str, int] = {}
        for match in matches:
            match: tuple[str, str] = match

            try:
                day = int(match[0])
                month = int(match[1])
            except ValueError:
                continue

            dayvars[f"${day}.{month}."] = month * 31 + day

        data = data.replace("$day", str(day_of_year))

        for s, t in dayvars.items():
            data = data.replace(s, str(t))

        return data

    def check_time(self, action: dict[str, Any]) -> bool:
        """Checks if the time set in the event matches the time we have

        Returns:
            bool: Whether the time matches
        """

        time_el = action.get("time", None)

        if time_el is None:
            return True

        time_str = str(time_el)

        time_str = self._replace_time(time_str)
        time_str = self._replace_date(time_str)

        # Evaluate the time string
        return bool(eval(time_str, {}, {}))

    def trigger(self) -> None:
        executed = False
        for req in self._actions:
            if not self.check_time(req):
                continue

            if req.get("else", None) is True and executed:
                continue

            path: str = req.get("path", None)
            if path is None:
                continue

            # Execute the
            fargs = path.strip("/").split(".")

            from backend.backend import BackendRequest

            BackendRequest.execute_backend(fargs, req.get("body", {}))
            executed = True
