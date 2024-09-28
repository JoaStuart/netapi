import time
from typing import Callable
from threading import Thread


class Schedule:
    _schedules: list["Schedule"] = []
    SLEEP_TIME = 0.2

    @staticmethod
    def add_schedule(schedule: "Schedule") -> None:
        Schedule._schedules.append(schedule)

    @staticmethod
    def start_scheduler() -> None:
        Thread(target=Schedule._tick_all, daemon=True).start()

    @staticmethod
    def _tick_all() -> None:
        while True:
            t = time.time()
            for s in Schedule._schedules:
                s.tick(t)

            time.sleep(Schedule.SLEEP_TIME)

    def __init__(self, interval: float, executor: Callable[[], None]) -> None:
        self._interval = interval
        self._executor = executor
        self._passed_time: float = 0

    def tick(self, time: float) -> None:
        self._passed_time += time

        if self._passed_time > self._interval:
            self._passed_time %= self._interval

            self._executor()
