import abc


class CleanUp(abc.ABC):
    @abc.abstractmethod
    def cleanup(self) -> None:
        pass
