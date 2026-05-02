"""Power tier encryption wrapper for Tune Hub."""

from __future__ import annotations

import json
import os
from typing import Callable, Dict


class PowerTierEncryption:
    """
    Per-user encryption for Power tier private tunes.

    Uses AES-256-GCM with per-user keys.
    Plaintext NEVER enters cloud DB.
    """

    KEY_SIZE = 32
    NONCE_SIZE = 12

    def __init__(self, key_provider: Callable[[str], bytes]) -> None:
        self.key_provider = key_provider

    def encrypt(self, user_id: str, tune_id: str, plaintext_payload: dict) -> bytes:
        """Encrypt a tune payload for a user."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            raise RuntimeError(
                "cryptography is required for PowerTierEncryption. "
                "Install with: pip install cryptography"
            )

        key = self.key_provider(user_id)
        aesgcm = AESGCM(key)
        nonce = os.urandom(self.NONCE_SIZE)
        associated_data = f"{user_id}:{tune_id}".encode("utf-8")
        plaintext = json.dumps(plaintext_payload).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce + ciphertext

    def decrypt(self, user_id: str, tune_id: str, encrypted_blob: bytes) -> dict:
        """Decrypt a tune payload for a user."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            raise RuntimeError(
                "cryptography is required for PowerTierEncryption. "
                "Install with: pip install cryptography"
            )

        key = self.key_provider(user_id)
        aesgcm = AESGCM(key)
        nonce = encrypted_blob[: self.NONCE_SIZE]
        ciphertext = encrypted_blob[self.NONCE_SIZE :]
        associated_data = f"{user_id}:{tune_id}".encode("utf-8")
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(plaintext.decode("utf-8"))


def derive_key_from_password(user_id: str, password: str) -> bytes:
    """Derive a 32-byte AES key from a user password."""
    try:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        raise RuntimeError("cryptography required")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=user_id.encode("utf-8"),
        iterations=480000,
    )
    return kdf.derive(password.encode("utf-8"))
