import abc
import time
from typing import Callable
from threading import Thread

from proj_types.singleton import singleton


@singleton
class Schedulor:
    SLEEP_TIME = 0.2

    def __init__(self) -> None:
        self._schedules: list["Executor"] = []
        self._last_tick = 0

        Thread(target=Schedulor._tick_all, name="Intervalometer", daemon=True).start()

    def add_schedule(self, executor: "Executor") -> None:
        self._schedules.append(executor)

    def remove_schedule(self, executor: "Executor") -> None:
        self._schedules.remove(executor)

    def _tick_all(self) -> None:
        while True:
            t = time.time()
            dt = t - self._last_tick
            self._last_tick = t
            for s in self._schedules:
                s.tick(t, dt)

            time.sleep(Schedulor.SLEEP_TIME)


class Executor(abc.ABC):
    def __init__(self, on_trigger: Callable[[], None]) -> None:
        super().__init__()

        self._on_trigger = on_trigger
        self.register()

    def register(self) -> None:
        Schedulor().add_schedule(self)

    def unregister(self) -> None:
        Schedulor().remove_schedule(self)

    def trigger(self) -> None:
        self._on_trigger()

    @abc.abstractmethod
    def tick(self, current_time: float, passed_time: float) -> None:
        pass


class TimedExecutor(Executor):
    def __init__(self, interval: float, on_trigger: Callable[[], None]) -> None:
        super().__init__(on_trigger)

        self._passed_time: float = 0
        self._interval: float = interval

    def tick(self, current_time: float, passed_time: float) -> None:
        self._passed_time += passed_time

        if self._passed_time > self._interval:
            self._passed_time %= self._interval

            self.trigger()


class DeferredExecutor(Executor):
    def __init__(self, wait_time: float, on_trigger: Callable[[], None]) -> None:
        super().__init__(on_trigger)

        self._wait_time = wait_time

    def tick(self, current_time: float, passed_time: float) -> None:
        self._wait_time -= passed_time

        if self._wait_time <= 0:
            self.trigger()
            self.unregister()


class UnixExecutor(Executor):
    def __init__(self, exec_time: float, on_trigger: Callable[[], None]) -> None:
        super().__init__(on_trigger)

        self._exec_time = exec_time

    def tick(self, current_time: float, passed_time: float) -> None:
        if current_time >= self._exec_time:
            self.trigger()
            self.unregister()
