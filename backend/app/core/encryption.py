# -*- coding: utf-8 -*-
"""
Encryption utilities for sensitive data.

Menggunakan enkripsi simetris Fernet untuk mengenkripsi data sensitif (misalnya API keys).
"""

from cryptography.fernet import Fernet


class EncryptionService:
    """Layanan enkripsi, untuk mengenkripsi dan mendekripsi data sensitif."""

    def __init__(self, encryption_key: str):
        """
        Menginisialisasi layanan enkripsi.

        Args:
            encryption_key: kunci enkripsi berkode Base64.
        """
        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        Mengenkripsi string teks polos.

        Args:
            plaintext: teks polos yang akan dienkripsi.

        Returns:
            String teks tersandi berkode Base64.
        """
        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Mendekripsi string teks tersandi.

        Args:
            ciphertext: teks tersandi berkode Base64.

        Returns:
            String teks polos hasil dekripsi.

        Raises:
            cryptography.fernet.InvalidToken: jika teks tersandi tidak valid atau
                kunci salah.
        """
        decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()


def generate_encryption_key() -> str:
    """
    Membuat kunci enkripsi Fernet baru.

    Returns:
        String kunci berkode Base64.
    """
    return Fernet.generate_key().decode()
