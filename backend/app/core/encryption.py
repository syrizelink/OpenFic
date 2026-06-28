# -*- coding: utf-8 -*-
"""
Encryption utilities for sensitive data.

使用 Fernet 对称加密来加密敏感数据（如 API keys）。
"""

from cryptography.fernet import Fernet


class EncryptionService:
    """加密服务，用于加密和解密敏感数据。"""

    def __init__(self, encryption_key: str):
        """
        初始化加密服务。

        Args:
            encryption_key: Base64 编码的加密密钥。
        """
        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        加密明文字符串。

        Args:
            plaintext: 待加密的明文。

        Returns:
            Base64 编码的密文字符串。
        """
        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        解密密文字符串。

        Args:
            ciphertext: Base64 编码的密文。

        Returns:
            解密后的明文字符串。

        Raises:
            cryptography.fernet.InvalidToken: 如果密文无效或密钥错误。
        """
        decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()


def generate_encryption_key() -> str:
    """
    生成一个新的 Fernet 加密密钥。

    Returns:
        Base64 编码的密钥字符串。
    """
    return Fernet.generate_key().decode()
