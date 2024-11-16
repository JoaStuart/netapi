import os
import socket

from webserver.encryption import Encryption, NoEncryption


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

        # Check if enough data is already in the buffer
        if len(self._recv_buff) >= size:
            data, self._recv_buff = self._recv_buff[:size], self._recv_buff[size:]
            return data

        # Not enough data in buffer
        data = self._recv_buff
        size -= len(self._recv_buff)
        self._recv_buff = b""

        # Receive data until
        while size > 0:
            data_enc = self._socket.recv(self.block_size())
            new_data = self._encryption.decrypt(data_enc)

            if len(new_data) >= size:
                data += new_data[:size]
                self._recv_buff = new_data[size:]
                break
            else:
                data += new_data
                size -= len(new_data)

        return data

    def send(self, data: bytes) -> None:
        data = self._send_buff + data

        largest_block = (len(data) // self.block_size()) * self.block_size()

        self._socket.sendall(self._encryption.encrypt(data[:largest_block]))
        self._send_buff = data[largest_block:]

    def flush(self) -> None:
        padding_needed = (
            self.block_size() - len(self._send_buff) % self.block_size()
        ) % self.block_size()

        data = self._send_buff + b"\0" * padding_needed
        self._send_buff = b""

        self._socket.sendall(self._encryption.encrypt(data))

    def sock(self) -> socket.socket:
        return self._socket

    def close(self) -> None:
        self._socket.close()
