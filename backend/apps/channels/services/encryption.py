import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


VERSION = "v1"


def _key():
    encoded = settings.CHANNEL_ENCRYPTION_KEY
    if not encoded:
        raise ImproperlyConfigured("CHANNEL_ENCRYPTION_KEY must be configured before storing channel credentials.")
    try:
        key = base64.urlsafe_b64decode(encoded.encode())
    except Exception as exc:
        raise ImproperlyConfigured("CHANNEL_ENCRYPTION_KEY must be URL-safe base64.") from exc
    if len(key) != 32:
        raise ImproperlyConfigured("CHANNEL_ENCRYPTION_KEY must decode to exactly 32 bytes.")
    return key


def encrypt_secret(value):
    if value in (None, ""):
        return ""
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, str(value).encode(), VERSION.encode())
    return f"{VERSION}:{base64.urlsafe_b64encode(nonce + ciphertext).decode()}"


def decrypt_secret(value):
    if not value:
        return ""
    try:
        version, encoded = value.split(":", 1)
        if version != VERSION:
            raise ValueError("Unsupported encrypted secret version.")
        payload = base64.urlsafe_b64decode(encoded.encode())
        return AESGCM(_key()).decrypt(payload[:12], payload[12:], VERSION.encode()).decode()
    except ImproperlyConfigured:
        raise
    except Exception as exc:
        raise ValueError("Unable to decrypt channel credential.") from exc

