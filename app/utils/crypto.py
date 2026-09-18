"""Symmetric encryption helpers for bot tokens.

Tokens are encrypted at rest using ``Fernet`` from the ``cryptography``
package. The encryption key is read from ``FERNET_KEY``; if it is missing a
deterministic development-only key is derived from ``WEBHOOK_SECRET`` so that
local setups work out of the box. **Never use the derived key in production.**
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoError(Exception):
    """Raised when encryption or decryption fails."""


def _derive_key(secret: str) -> bytes:
    """Derive a deterministic 32-byte Fernet key from a secret string.

    This is a convenience for local development only.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class TokenCipher:
    """Encrypt/decrypt sensitive values (e.g. bot tokens)."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        """Return the encrypted form of ``value`` as a text token."""
        if not value:
            raise CryptoError("Cannot encrypt an empty value")
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        """Return the decrypted plain text of ``value``."""
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:  # pragma: no cover - defensive
            raise CryptoError("Failed to decrypt token") from exc


@lru_cache
def get_cipher() -> TokenCipher:
    """Return a cached :class:`TokenCipher` built from application settings."""
    settings = get_settings()
    if settings.fernet_key:
        key = settings.fernet_key.encode("ascii")
    else:
        key = _derive_key(settings.webhook_secret)
    return TokenCipher(key)


def redact(value: str, visible: int = 4) -> str:
    """Return a redacted version of a secret for safe logging.

    Example: ``redact("1234567890")`` -> ``"1234…"``.
    """
    if not value:
        return ""
    return f"{value[:visible]}…"
