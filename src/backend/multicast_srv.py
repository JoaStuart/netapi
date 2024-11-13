import base64
import os
import socket
import struct
from threading import Thread
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding

import locations


class MulticastServer:
    KEY_SIZE = 2048

    def __init__(self) -> None:
        self._ip = self._get_local_addr()
        self._group_addr: tuple[str, int] = (
            locations.MULTICAST_GROUP,
            locations.MULTICAST_PORT,
        )

        self._key_path = os.path.join(locations.RESOURCES, "multicast_priv.rsa")
        self._private_key = self._load_key()

    def _load_key(self) -> rsa.RSAPrivateKey:
        """Loads the private RSA key from file or generates a new one if none is found

        Returns:
            rsa.RSAPrivateKey: The private key for this Multicast instance
        """

        if (key := self._load_keyfile()) != None:
            return key

        key = rsa.generate_private_key(
            public_exponent=65537, key_size=MulticastServer.KEY_SIZE
        )
        self._write_keys(key)

        return key

    def _load_keyfile(self) -> rsa.RSAPrivateKey | None:
        """Tries to load the existing key from file

        Returns:
            rsa.RSAPrivateKey | None: The key loaded or None if file is not found or not a RSA private key.
        """

        if not os.path.isfile(self._key_path):
            return None

        with open(self._key_path, "rb") as rf:
            data = rf.read()

        key = serialization.load_pem_private_key(data, None, default_backend())

        if not isinstance(key, rsa.RSAPrivateKey):
            return None

        return key

    def _write_keys(self, priv_key: rsa.RSAPrivateKey) -> None:
        """Writes the given private key and its public key to file

        Args:
            priv_key (rsa.RSAPrivateKey): The private key to write
        """

        priv_bytes = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with open(self._key_path, "wb") as wf:
            wf.write(priv_bytes)

        publ_bytes = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with open(os.path.join(locations.PUBLIC, "multicast.rsa"), "wb") as wf:
            wf.write(publ_bytes)

    def _get_local_addr(self) -> str:
        """Retrieves the local IP address of this device

        Returns:
            str: The local IP address
        """

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Connect to an external IP
            local_ip = s.getsockname()[0]
        return local_ip

    def background_listen(self) -> None:
        """Starts a background thread listening to Multicast searches"""

        Thread(target=self._listen, name="SSDP", daemon=True).start()

    def _listen(self) -> None:
        """Target method of listening thread"""

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.bind(("", locations.MULTICAST_PORT))

        mreq = struct.pack(
            "4sl", socket.inet_aton(locations.MULTICAST_GROUP), socket.INADDR_ANY
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        while True:
            self._handle_request(*sock.recvfrom(4096), sock)

    def _check_headers(self, headers: dict[str, str]) -> bool:
        """Checks the given headers if the device sending the request is searching this device

        Args:
            headers (dict[str, str]): The headers of the SSDP request

        Returns:
            bool: Whether the sending device is searching this device
        """

        return (
            headers.get("st", "")
            == f"{locations.MULTICAST_LIBRARY}:{locations.MULTICAST_SERVICE}"
            and headers.get("usn", "") == locations.MULTICAST_SERVICE
            and headers.get("man", "").lower() == '"ssdp:discover"'
            and len(headers.get("authorization", "")) > 0
        )

    def _handle_request(
        self, data: bytes, addr: tuple[str, int], sock: socket.socket
    ) -> None:
        """Method to handle any incoming Multicasts

        Args:
            data (bytes): The raw data sent by the device
            addr (tuple[str, int]): The address of the device
            sock (socket.socket): The socket to respond to
        """

        lines = data.decode().split("\r\n")
        status = lines.pop(0)
        headers: dict[str, str] = {}

        for l in lines:
            if ":" not in l:
                continue
            args = l.split(":", 1)

            headers[args[0].strip().lower()] = args[1].strip()

        if not status.startswith("M-SEARCH * HTTP/1.1") or not self._check_headers(
            headers
        ):
            return

        sock.sendto(self._reply_msg(headers["authorization"]), addr)

    def _reply_msg(self, enc_text: str) -> bytes:
        """Sends the reply message

        Args:
            enc_text (str): The authorization text sent by the client

        Returns:
            bytes: The message to send back
        """

        encrypted = self._private_key.sign(
            enc_text.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )

        location_msg = "\r\n".join(
            [
                "HTTP/1.1 200 OK",
                f"ST: {locations.MULTICAST_LIBRARY}:{locations.MULTICAST_SERVICE}",
                f"USN: {locations.MULTICAST_SERVICE}",
                f"Location: {self._ip}",
                "Cache-Control: no-cache",
                f"Authorization: {base64.standard_b64encode(encrypted).decode()}",
            ]
        )

        return location_msg.encode()
