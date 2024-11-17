import abc
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class Encryption(abc.ABC):

    @abc.abstractmethod
    def block_size(self) -> int:
        """
        Returns:
            int: The block size used by this encryption
        """

        pass

    @abc.abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        """Decrypts the provided data

        Args:
            data (bytes): The data to be decrypted, must be full block(s)

        Returns:
            bytes: The decrypted data
        """

        pass

    @abc.abstractmethod
    def encrypt(self, data: bytes) -> bytes:
        """Encrypts the provided data

        Args:
            data (bytes): The data to be encrypted, must be full block(s)

        Returns:
            bytes: The encrypted data
        """

        pass


class NoEncryption(Encryption):

    def __init__(self) -> None:
        """Empty encryption method used as default"""

        super().__init__()

    def block_size(self) -> int:
        """
        Returns:
            int: The block size used by this encryption
        """

        return 1

    def decrypt(self, data: bytes) -> bytes:
        """Decrypts the provided data

        Args:
            data (bytes): The data to be decrypted, must be full block(s)

        Returns:
            bytes: The decrypted data
        """

        return data

    def encrypt(self, data: bytes) -> bytes:
        """Encrypts the provided data

        Args:
            data (bytes): The data to be encrypted, must be full block(s)

        Returns:
            bytes: The encrypted data
        """

        return data


class AesEncryption(Encryption):
    @staticmethod
    def key_len() -> int:
        """
        Returns:
            int: The length of key required for this encryption method
        """

        return 32

    @staticmethod
    def iv_len() -> int:
        """
        Returns:
            int: The length of IV string required for this encryption method
        """

        return 16

    def __init__(self, key: bytes, iv: bytes) -> None:
        """An encryption method using AES256 and CBC

        Args:
            key (bytes): The key to use
            iv (bytes): The IV string to use
        """

        self._aes = algorithms.AES256(key)
        self._cipher = Cipher(algorithm=self._aes, mode=modes.CBC(iv))

    def block_size(self) -> int:
        """
        Returns:
            int: The block size used by this encryption
        """

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
