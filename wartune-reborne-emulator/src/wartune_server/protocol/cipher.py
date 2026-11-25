"""Cifra de fluxo XOR do ByteSocket (cliente 7Road).

Reimplementa ``yishi.comm.ByteSocket.send`` / ``PackageIn.loadE``. A chave tem
8 bytes e muda a cada byte cifrado, *continuando entre pacotes*: por isso cada
direção da conexão tem a sua instância e ela nunca pode ser usada por duas
corrotinas ao mesmo tempo (ver ``net.session``).
"""

from __future__ import annotations

from typing import Final

DEFAULT_KEY: Final[bytes] = bytes([174, 191, 86, 120, 171, 205, 239, 241])
KEY_SIZE: Final[int] = 8


class StreamCipher:
    """Estado de chave de uma direção (envio ou recebimento)."""

    __slots__ = ("_key", "is_h5")

    def __init__(self, key: bytes = DEFAULT_KEY, *, is_h5: bool = False) -> None:
        self._key = bytearray(self._validate(key))
        self.is_h5 = is_h5

    @staticmethod
    def _validate(key: bytes) -> bytes:
        if len(key) != KEY_SIZE:
            raise ValueError(f"chave precisa ter {KEY_SIZE} bytes, recebeu {len(key)}")
        return key

    @property
    def key(self) -> bytes:
        return bytes(self._key)

    def reset(self, key: bytes = DEFAULT_KEY) -> None:
        self._key[:] = self._validate(key)

    def encrypt(self, plain: bytes) -> bytes:
        key = self._key
        out = bytearray(len(plain))
        for i, byte in enumerate(plain):
            if i == 0:
                out[0] = byte ^ key[0]
                continue
            k = i % KEY_SIZE
            key[k] = ((key[k] + out[i - 1]) ^ i) & 0xFF
            out[i] = ((byte ^ key[k]) + out[i - 1]) & 0xFF
        return bytes(out)

    def decrypt(self, cipher: bytes) -> bytes:
        return self._decrypt(cipher, self._key, self.is_h5)

    def peek(self, cipher: bytes) -> bytes:
        """Decifra sem avançar o estado (usado para ler o cabeçalho antes do pacote completo)."""
        return self._decrypt(cipher, bytearray(self._key), self.is_h5)

    @staticmethod
    def _decrypt(cipher: bytes, key: bytearray, is_h5: bool = False) -> bytes:
        out = bytearray(len(cipher))
        for i, byte in enumerate(cipher):
            if i == 0:
                out[0] = byte ^ key[0]
                continue
            k = i % KEY_SIZE
            prev = cipher[i - 1]
            key[k] = ((key[k] + prev) ^ i) & 0xFF
            if is_h5:
                out[i] = (byte ^ ((key[k] + prev) & 0xFF)) & 0xFF
            else:
                out[i] = ((byte - prev) & 0xFF) ^ key[k]
        return bytes(out)
