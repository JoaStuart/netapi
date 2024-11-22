import hashlib
import math
import random


class DHAlgorithm:
    def __init__(self) -> None:
        self._g = 2
        self._p = 0xFFFFFFFF_FFFFFFFF_C90FDAA2_2168C234_C4C6628B_80DC1CD1_29024E08_8A67CC74_020BBEA6_3B139B22_514A0879_8E3404DD_EF9519B3_CD3A431B_302B0A6D_F25F1437_4FE1356D_6D51C245_E485B576_625E7EC6_F44C42E9_A637ED6B_0BFF5CB6_F406B7ED_EE386BFB_5A899FA5_AE9F2411_7C4B1FE6_49286651_ECE45B3D_C2007CB8_A163BF05_98DA4836_1C55D39A_69163FA8_FD24CF5F_83655D23_DCA3AD96_1C62F356_208552BB_9ED52907_7096966D_670C354E_4ABC9804_F1746C08_CA18217C_32905E46_2E36CE3B_E39E772C_180E8603_9B2783A2_EC07A28F_B5C55DF0_6F4C52C9_DE2BCBF6_95581718_3995497C_EA956AE5_15D22618_98FA0510_15728E5A_8AACAA68_FFFFFFFF_FFFFFFFF
        self._q = self._p // 2

        self._K: int | None = None

    def make_enc_key(self, length: int) -> bytes:
        """Makes the encryption key to be used in further conversation

        Args:
            length (int): The length of key required

        Returns:
            bytes: The generated key
        """

        return self._make_crypt_str(b"KEY", length)

    def make_iv_str(self, length: int) -> bytes:
        """Makes the IV string to be used in further conversation

        Args:
            length (int): The length of IV required

        Returns:
            bytes: The generated IV string
        """

        return self._make_crypt_str(b"IVS", length)

    def _make_crypt_str(self, id: bytes, length: int) -> bytes:
        """Makes a crypto key using the exchanged `K` using the id and length

        Args:
            id (bytes): The ID of the string to generate
            length (int): The length of data to return. Maximum 32 bytes.

        Raises:
            ValueError: When the key exchange has not yet been performed or the length is more than maximum

        Returns:
            bytes: The generated crypto key
        """

        if self._K is None:
            raise ValueError("You need to exchange keys first")
        if length > 32:
            raise ValueError("The requested length is too long")

        # Hashes `K`(binary) + `ID`
        h_data = hashlib.sha256(
            self._K.to_bytes(length=(self._K.bit_length() + 7) // 8) + id
        ).digest()

        print(f"K: {self._K}")
        return h_data[:length]


class DHServer(DHAlgorithm):
    def __init__(self) -> None:
        super().__init__()

        self._y = random.randint(1, self._q - 1)

    def read_e(self, e: int) -> None:
        """
        Args:
            e (int): Value of `e` sent by the client
        """

        print(f"E: {e}")
        self._K = pow(e, self._y, self._p)

    def get_f(self) -> int:
        """
        Returns:
            int: The local value of `f`
        """

        f = pow(self._g, self._y, self._p)
        print(f"F: {f}")
        return f


class DHClient(DHAlgorithm):
    def __init__(self) -> None:
        super().__init__()

        self._x = random.randint(2, self._q - 1)

    def read_f(self, f: int):
        """
        Args:
            f (int): Value of `f` sent by the server
        """

        self._K = pow(f, self._x, self._p)

    def get_e(self) -> int:
        """
        Returns:
            int: The local value of `e`
        """

        return pow(self._g, self._x, self._p)
