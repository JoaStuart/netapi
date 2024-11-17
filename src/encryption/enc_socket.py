import os
import socket

from encryption.encryption import Encryption, NoEncryption


class EncryptedSocket:
    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock
        self._recv_buff = b""
        self._send_buff = b""
        self._encryption: Encryption = NoEncryption()

    def update_encryption(self, encryption: Encryption) -> None:
        self._encryption = encryption

    def block_size(self) -> int:
        return self._encryption.block_size()

    def recv(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("Size is less than zero")
        elif size == 0:
            return b""

        data = self._recv_buff
        block_size = self.block_size()

        while len(data) < size:
            encrypted_block = self._socket.recv(block_size)
            if not encrypted_block:
                break

            decrypted_block = self._encryption.decrypt(encrypted_block)
            data += decrypted_block

        self._recv_buff, return_data = data[size:], data[:size]
        return return_data

    def send(self, data: bytes) -> None:
        data = self._send_buff + data
        block_size = self.block_size()

        largest_block = (len(data) // block_size) * block_size

        if largest_block > 0:
            self._socket.sendall(self._encryption.encrypt(data[:largest_block]))

        self._send_buff = data[largest_block:]

    def flush(self) -> None:
        block_size = self.block_size()

        padding_needed = (block_size - len(self._send_buff) % block_size) % block_size
        data = self._send_buff + b"\0" * padding_needed  # Pad with null bytes
        self._send_buff = b""

        self._socket.sendall(self._encryption.encrypt(data))

    def sock(self) -> socket.socket:
        return self._socket

    def close(self) -> None:
        self._socket.close()
