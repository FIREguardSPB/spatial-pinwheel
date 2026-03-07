"""
P8-02: Token encryption at rest using Fernet (symmetric encryption).

If TOKEN_ENCRYPTION_KEY is set and `cryptography` is installed → encrypt/decrypt.
If not → plaintext fallback with warning.

Usage:
    from core.security.crypto import encrypt_token, decrypt_token
    encrypted = encrypt_token("sk-ant-api03-...")
    original  = decrypt_token(encrypted)

Key generation:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_fernet_instance = None
_initialized = False

# Prefix to distinguish encrypted values from plaintext
_ENCRYPTED_PREFIX = "enc:v1:"


def _get_fernet():
    """Lazy-init Fernet instance from config."""
    global _fernet_instance, _initialized
    if _initialized:
        return _fernet_instance

    _initialized = True
    try:
        from core.config import settings
        key = settings.TOKEN_ENCRYPTION_KEY
        if not key:
            logger.debug("TOKEN_ENCRYPTION_KEY not set — tokens stored in plaintext")
            return None

        from cryptography.fernet import Fernet
        _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
        logger.info("Token encryption enabled (Fernet)")
        return _fernet_instance
    except ImportError:
        logger.warning(
            "cryptography package not installed — token encryption disabled. "
            "Install: pip install cryptography"
        )
        return None
    except Exception as e:
        logger.error("Failed to initialize Fernet: %s — tokens will be plaintext", e)
        return None


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a token value. Returns encrypted string with prefix,
    or original value if encryption not available.
    """
    if not plaintext:
        return plaintext

    f = _get_fernet()
    if f is None:
        return plaintext

    try:
        encrypted = f.encrypt(plaintext.encode("utf-8"))
        return _ENCRYPTED_PREFIX + encrypted.decode("utf-8")
    except Exception as e:
        logger.warning("Token encryption failed: %s", e)
        return plaintext


def decrypt_token(stored_value: str) -> str:
    """
    Decrypt a token value. Handles both encrypted and plaintext values.
    """
    if not stored_value:
        return stored_value

    # Not encrypted — return as-is
    if not stored_value.startswith(_ENCRYPTED_PREFIX):
        return stored_value

    f = _get_fernet()
    if f is None:
        logger.warning("Encrypted token found but decryption not available")
        return ""  # Can't decrypt without key — return empty rather than broken ciphertext

    try:
        ciphertext = stored_value[len(_ENCRYPTED_PREFIX):]
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error("Token decryption failed: %s", e)
        return ""


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return value.startswith(_ENCRYPTED_PREFIX) if value else False
