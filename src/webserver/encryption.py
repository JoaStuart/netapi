import abc
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class Encryption(abc.ABC):

    @abc.abstractmethod
    def block_size(self) -> int:
        pass

    @abc.abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        pass

    @abc.abstractmethod
    def encrypt(self, data: bytes) -> bytes:
        pass


class NoEncryption(Encryption):
    def block_size(self) -> int:
        return 1

    def decrypt(self, data: bytes) -> bytes:
        return data

    def encrypt(self, data: bytes) -> bytes:
        return data


class AesEncryption(Encryption):
    def __init__(self, key: bytes, iv: bytes) -> None:
        self._aes = algorithms.AES256(key)
        self._cipher = Cipher(algorithm=self._aes, mode=modes.CBC(iv))

    def block_size(self) -> int:
        return self._aes.block_size // 8

    def encrypt(self, data: bytes) -> bytes:
        return self._cipher.encryptor().update(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._cipher.decryptor().update(data)
