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
    @staticmethod
    def key_len() -> int:
        return 32

    @staticmethod
    def iv_len() -> int:
        return 16

    def __init__(self, key: bytes, iv: bytes) -> None:
        self._aes = algorithms.AES256(key)
        self._cipher = Cipher(algorithm=self._aes, mode=modes.CBC(iv))

    def block_size(self) -> int:
        return self._aes.block_size // 8

    def encrypt(self, data: bytes) -> bytes:
        """Encrypts the data, while using a different encryptor for each chunk

        Args:
            data (bytes): The data to be encrypted, must be full block(s)

        Returns:
            bytes: The encrypted data
        """
        encrypted_data = b""

        for i in range(0, len(data), self.block_size()):
            chunk = data[i : i + self.block_size()]

            encryptor = self._cipher.encryptor()
            encrypted_data += encryptor.update(chunk) + encryptor.finalize()

        return encrypted_data

    def decrypt(self, data: bytes) -> bytes:
        """Decrypts the data, while using a different decryptor for each chunk

        Args:
            data (bytes): The data to be decrypted, must be full block(s)

        Returns:
            bytes: The decrypted data
        """

        decrypted_data = b""

        for i in range(0, len(data), self.block_size()):
            chunk = data[i : i + self.block_size()]

            decryptor = self._cipher.decryptor()
            decrypted_data += decryptor.update(chunk) + decryptor.finalize()

        return decrypted_data
