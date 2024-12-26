import abc
import zlib
import gzip


class Compression(abc.ABC):
    def __init__(self) -> None:
        super().__init__()
        
    @abc.abstractmethod
    def compress(self, data: bytes) -> bytes:
        pass
    
    @abc.abstractmethod
    def name(self) -> str:
        pass
    
    @staticmethod
    def algorithms() -> "list[Compression]":
        return [
            Deflate(),
            Gzip(),
        ]
    
class Deflate(Compression):
    def compress(self, data: bytes) -> bytes:
        return zlib.compress(data)
    
    def name(self) -> str:
        return "deflate"
    
class Gzip(Compression):
    def compress(self, data: bytes) -> bytes:
        return gzip.compress(data)
    
    def name(self) -> str:
        return "gzip"
