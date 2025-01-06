"""
@internal(B) Function for securely storing
             data inside a vault
"""

import gzip
import json
import os
from device.api import APIFunct, APIResult
import locations
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding


class Vault(APIFunct):
    KEY_SIZE = 4096
    VAULT_FILE = os.path.join(locations.RESOURCES, "vault_data.enc")
    KEY_FILE = os.path.join(locations.RESOURCES, "vault_key.pem")
    LABELS_FILE = os.path.join(locations.RESOURCES, "vault_labels.json")
    PADDING = padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
    )

    def api(self) -> APIResult:
        # Check if we got the request in the secure context
        if self.request is None or not self.request.secure:
            return APIResult.by_msg(
                "Vault requests have to be made via SECURE requests", False
            )

        try:
            # Read the keys of the data stored in the vault
            if len(self.args) == 0:
                return self._labels()

            if self.args[0] == "create":
                # Create a new vault
                return self._create_vault()

            elif self.args[0] == "write":
                # Write the contents into the vault
                return self._write()

            elif self.args[0] == "read":
                # Read the data from the vault
                return self._read()

        except Exception as e:
            return APIResult.by_exception(e)

        return APIResult.by_msg("Operation not found!")

    def _create_vault(self) -> APIResult:
        """Creates a private key and vault and stores them into files

        Returns:
            APIResult: The result of this action
        """

        if os.path.isfile(self.VAULT_FILE) and not (
            len(self.args) == 2 and self.args[1] == "overwrite"
        ):
            return APIResult.by_msg(
                "A vault file already exists. To overwrite, use `/vault.create.overwrite`",
                False,
            )

        if "password" not in self.body:
            return APIResult.by_msg("You need to specify a key password!", False)

        password = str(self.body["password"])

        private_key = rsa.generate_private_key(65537, self.KEY_SIZE)

        self._write_key(private_key, password.encode("utf-8"))

        self._write_vault(private_key, {})

        return APIResult.by_success(True)

    def _check_vault(self) -> bool:
        files = [self.VAULT_FILE, self.KEY_FILE, self.LABELS_FILE]
        return all([os.path.isfile(f) for f in files])

    def _write_key(self, private_key: rsa.RSAPrivateKey, password: bytes) -> None:
        """Writes the provided rsa private key into file using the provided password

        Args:
            private_key (rsa.RSAPrivateKey): The private rsa key to write
            password (bytes): The password to encrypt the key with
        """

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        )

        with open(self.KEY_FILE, "wb") as wf:
            wf.write(private_bytes)

    def _read_key(self, password: bytes) -> rsa.RSAPrivateKey:
        """Reads the private key from file using the provided password

        Args:
            password (bytes): The password used to decrypt the key

        Raises:
            ValueError: Upon failure to load the key

        Returns:
            rsa.RSAPrivateKey: The private rsa key read from file
        """

        with open(self.KEY_FILE, "rb") as rf:
            key_data = rf.read()

        private_key = serialization.load_pem_private_key(
            key_data, password, default_backend()
        )

        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError(f"Could not load key in right format: {type(private_key)}")

        return private_key

    def _write_vault(
        self, private_key: rsa.RSAPrivateKey, data: dict[str, str]
    ) -> None:
        """Writes the provided data into the vault, overwriting the old data

        Args:
            private_key (rsa.RSAPrivateKey): The key to encrypt the vault with
            data (dict[str, str]): The data to store inside the vault
        """

        public_key = private_key.public_key()

        data_bin = json.dumps(data).encode("utf-8")
        data_cmp = gzip.compress(data_bin)
        data_enc = public_key.encrypt(data_cmp, padding=self.PADDING)

        with open(self.VAULT_FILE, "wb") as wf:
            wf.write(data_enc)

    def _write_labels(self, data: dict[str, str]) -> None:
        """Updates the labels cache with the labels of the data

        Args:
            data (dict[str, str]): The data stored inside the vault
        """

        data_keys = [k for k in data.keys()]

        with open(self.LABELS_FILE, "w") as wf:
            wf.write(json.dumps(data_keys))

    def _read_labels(self) -> list[str]:
        """Reads the labels of the data stored inside the vault

        Raises:
            ValueError: Upon receiving labels in an unknown format

        Returns:
            list[str]: The labels of data stored inside the vault
        """

        with open(self.LABELS_FILE, "r") as rf:
            data = rf.read()

        labels = json.loads(data)

        if not isinstance(labels, list):
            raise ValueError(f"Could not load labels as list: {type(labels)}")

        return labels

    def _read_vault(self, private_key: rsa.RSAPrivateKey) -> dict[str, str]:
        """Reads the data entries inside the vault using the provided key

        Args:
            private_key (rsa.RSAPrivateKey): The key used to decrypt the vault

        Raises:
            ValueError: Upon failure when loading the vault data

        Returns:
            dict[str, str]: The data stored inside the vault
        """

        with open(self.VAULT_FILE, "rb") as rf:
            vault_enc = rf.read()

        vault_cmp = private_key.decrypt(vault_enc, padding=self.PADDING)

        vault_json = gzip.decompress(vault_cmp)
        vault_data = json.loads(vault_json)

        if not isinstance(vault_data, dict):
            raise ValueError(
                f"Could not load vault in right format: {type(vault_data)}"
            )

        return vault_data

    def _read(self) -> APIResult:
        """Reads all data from the vault and encodes it into an APIResponse

        Returns:
            APIResult: The response to this action
        """

        if not self._check_vault():
            return APIResult.by_msg("No vault found!", False)

        if "password" not in self.body:
            return APIResult.by_msg("No password provided!", False)

        password = str(self.body["password"])

        private_key = self._read_key(password.encode("utf-8"))

        vault_data = self._read_vault(private_key)

        return APIResult.by_json(vault_data)

    def _write(self) -> APIResult:
        """Writes the data provided in the body into the vault
        taking the old values into consideration

        Returns:
            APIResult: The result of this action
        """

        if not self._check_vault():
            return APIResult.by_msg("No vault found!", False)

        if "password" not in self.body:
            return APIResult.by_msg("No password provided!", False)

        password = str(self.body["password"])
        private_key = self._read_key(password.encode("utf-8"))

        if "vault" not in self.body:
            return APIResult.by_msg("No data to write!", False)

        vault_data = self.body["vault"]
        vault_old = self._read_vault(private_key)
        vault_new = vault_old | vault_data

        self._write_vault(private_key, vault_new)
        self._write_labels(vault_new)
        return APIResult.by_success(True)

    def _labels(self) -> APIResult:
        """Reads the labels of the data stored inside the vault

        Returns:
            APIResult: The result of this operation
        """

        if not self._check_vault():
            return APIResult.by_msg("No vault found!", False)

        return APIResult.by_json(self._read_labels(), True)
