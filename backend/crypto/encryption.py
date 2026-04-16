"""
AES-256 Encryption / Decryption (EAX mode — authenticated encryption).
Keys are stored as hex strings in the database, linked to each file.
"""

import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


def encrypt_file(file_bytes: bytes):
    """
    Encrypt raw file bytes with AES-256-EAX.

    Returns:
        encrypted_bytes  (bytes) : nonce(16) + tag(16) + ciphertext
        key_hex          (str)   : 64-char hex string of the 32-byte key
    """
    key = get_random_bytes(32)              # 256-bit key
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(file_bytes)

    # Pack: nonce(16) | tag(16) | ciphertext
    encrypted_bytes = cipher.nonce + tag + ciphertext
    key_hex = key.hex()
    return encrypted_bytes, key_hex


def decrypt_file(encrypted_bytes: bytes, key_hex: str):
    """
    Decrypt bytes that were encrypted by encrypt_file().

    Returns:
        original_bytes (bytes) on success.
    Raises:
        ValueError if authentication fails (tampered data or wrong key).
    """
    key = bytes.fromhex(key_hex)
    nonce      = encrypted_bytes[:16]
    tag        = encrypted_bytes[16:32]
    ciphertext = encrypted_bytes[32:]

    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    try:
        data = cipher.decrypt_and_verify(ciphertext, tag)
    except ValueError:
        raise ValueError("Decryption failed: data may be tampered or key is wrong.")
    return data
