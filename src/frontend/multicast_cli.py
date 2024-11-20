import base64
import hashlib
import logging
import os
import socket
import struct
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding

import locations


from log import LOG


class MulticastClient:
    def __init__(self) -> None:
        self._key_path = os.path.join(locations.RESOURCES, "multicast_publ.rsa")

        self._priv_key = self._load_key()
        self._enc_text = self._make_random_text()

    def _load_key(self) -> rsa.RSAPublicKey:
        """Loads the public key for the server

        Raises:
            FileNotFoundError: If no key was found
            TypeError: If the file found does not contain a key

        Returns:
            rsa.RSAPublicKey: The public key of the server we are trying to connect to
        """

        if not os.path.isfile(self._key_path):
            raise FileNotFoundError("No public key found!")

        with open(self._key_path, "rb") as rf:
            data = rf.read()

        key = serialization.load_pem_public_key(data, None)

        if not isinstance(key, rsa.RSAPublicKey):
            raise TypeError("The loaded key is not an RSA public key.")

        return key

    def _make_random_text(self) -> str:
        """Generates a random text and hashes it

        Returns:
            str: The random hash used for server validation
        """

        rng_bytes = os.urandom(64)

        h = hashlib.sha1(rng_bytes)
        return h.hexdigest()

    def _verify(self, response: dict[str, str]) -> bool:
        """Verifies that the gotten response is from the server we have the public key of

        Args:
            response (dict[str, str]): The headers of the server response

        Returns:
            bool: Whether the verification suceeded and the response was sent by the server we are searching
        """

        if "authorization" not in response:
            return False

        try:
            self._priv_key.verify(
                base64.standard_b64decode(response["authorization"]),
                self._enc_text.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    def _handle_response(self, data: bytes) -> str | None:
        """Handles an incoming response

        Args:
            data (bytes): The raw data of the response

        Returns:
            str | None: The IP of the server or None if the reply is from another server
        """

        lines = data.decode().split("\r\n")

        status = lines.pop(0)
        headers: dict[str, str] = {}

        for l in lines:
            if ":" not in l:
                continue

            args = l.split(":", 1)
            headers[args[0].lower().strip()] = args[1].strip()

        if (
            not status.startswith("HTTP/1.1 200")
            or "location" not in headers
            or headers.get("usn", "") != locations.MULTICAST_SERVICE
            or not headers.get("st", "").startswith(locations.MULTICAST_LIBRARY)
            or not self._verify(headers)
        ):
            return

        LOG.info("Found server at %s", headers["location"])
        return headers["location"]

    def _interface_addresses(self, family: socket.AddressFamily = socket.AF_INET):
        """Generator for getting all interface addresses this device is connected to

        Args:
            family (socket.AddressFamily, optional): The address family we are searching the addresses of. Defaults to socket.AF_INET.

        Yields:
            str: The IP of each interface this device is connected to
        """

        for fam, _, _, _, sockaddr in socket.getaddrinfo("", None):
            if family == fam:
                yield sockaddr[0]

    def request(self, timeout: float = 5) -> str | None:
        """Sends a SSDP search for the server

        Returns:
            str | None: The IP of the server or None if the server could not be found
        """

        LOG.info("Searching server...")
        request_msg = "\r\n".join(
            [
                "M-SEARCH * HTTP/1.1",
                f"ST: {locations.MULTICAST_LIBRARY}:{locations.MULTICAST_SERVICE}",
                f"USN: {locations.MULTICAST_SERVICE}",
                'MAN: "ssdp:discover"',
                f"Authorization: {self._enc_text}",
                "",
            ]
        ).encode()

        socket.setdefaulttimeout(timeout)
        for addr in self._interface_addresses():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.bind((addr, 0))

            sock.sendto(
                request_msg, (locations.MULTICAST_GROUP, locations.MULTICAST_PORT)
            )

            while True:
                try:
                    data = sock.recv(1024)
                except socket.timeout:
                    break
                else:
                    if ip := self._handle_response(data):
                        return ip
