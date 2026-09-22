from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.channels.models import (
    AmazonChannelCredential,
    CdiscountChannelCredential,
    EbayChannelCredential,
    OttoChannelCredential,
    KauflandChannelCredential,
    WooCommerceChannelCredential,
    ChannelStatus,
)
from .encryption import encrypt_secret


MODEL_BY_PLATFORM = {
    "amazon": AmazonChannelCredential,
    "ebay": EbayChannelCredential,
    "cdiscount": CdiscountChannelCredential,
    "woocommerce": WooCommerceChannelCredential,
    "otto": OttoChannelCredential,
    "kaufland": KauflandChannelCredential,
}
RELATED_BY_PLATFORM = {
    "amazon": "amazon_credentials",
    "ebay": "ebay_credentials",
    "cdiscount": "cdiscount_credentials",
    "woocommerce": "woocommerce_credentials",
    "otto": "otto_credentials",
    "kaufland": "kaufland_credentials",
}
FIELDS = {
    "amazon": ({"seller_id", "refresh_token"}, {"seller_id", "refresh_token", "access_token", "access_token_expires_at"}),
    "ebay": ({"refresh_token"}, {"ebay_user_id", "refresh_token", "access_token", "access_token_expires_at"}),
    "cdiscount": ({"seller_id", "client_id", "client_secret"}, {"seller_id", "client_id", "client_secret"}),
    "woocommerce": ({"store_url", "consumer_key", "consumer_secret"}, {"store_url", "consumer_key", "consumer_secret", "verify_ssl"}),
    "otto": ({"client_id", "client_secret"}, {"client_id", "client_secret"}),
    "kaufland": ({"client_key", "client_secret"}, {"client_key", "client_secret"}),
}
SECRET_FIELDS = {
    "amazon": {"refresh_token", "access_token"},
    "ebay": {"refresh_token", "access_token"},
    "cdiscount": {"client_id", "client_secret"},
    "woocommerce": {"consumer_key", "consumer_secret"},
    "otto": {"client_id", "client_secret"},
    "kaufland": {"client_key", "client_secret"},
}


def _existing(channel):
    try:
        return getattr(channel, RELATED_BY_PLATFORM[channel.platform.code])
    except ObjectDoesNotExist:
        return None


def normalize_store_url(value):
    value = value.strip().rstrip("/")
    URLValidator(schemes=("https",))(value)
    parts = urlsplit(value)
    if parts.scheme != "https":
        raise serializers.ValidationError("WooCommerce store URL must use HTTPS.")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def validate_credential_payload(platform_code, payload, partial=False):
    if platform_code not in FIELDS:
        raise serializers.ValidationError({"credentials": "Unsupported channel platform."})
    if not isinstance(payload, dict):
        raise serializers.ValidationError({"credentials": "Expected an object."})
    required, allowed = FIELDS[platform_code]
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise serializers.ValidationError({"credentials": f"Fields do not match {platform_code}: {', '.join(unknown)}"})
    if not partial:
        missing = sorted(field for field in required if not payload.get(field))
        if missing:
            raise serializers.ValidationError({"credentials": f"Required fields: {', '.join(missing)}"})
    result = dict(payload)
    if platform_code == "woocommerce" and "store_url" in result:
        try:
            result["store_url"] = normalize_store_url(result["store_url"])
        except Exception as exc:
            if isinstance(exc, serializers.ValidationError):
                raise
            raise serializers.ValidationError({"credentials": "Enter a valid WooCommerce HTTPS store URL."}) from exc
    return result


@transaction.atomic
def set_channel_credentials(channel, payload, partial=False):
    platform_code = channel.platform.code
    existing = _existing(channel)
    clean = validate_credential_payload(platform_code, payload, partial=partial and existing is not None)
    encrypted = {
        key: encrypt_secret(value) if key in SECRET_FIELDS[platform_code] else value
        for key, value in clean.items()
    }
    model = MODEL_BY_PLATFORM[platform_code]
    credential, _ = model.objects.update_or_create(channel=channel, defaults=encrypted)
    if platform_code in {"cdiscount", "woocommerce", "otto", "kaufland"}:
        channel.status = ChannelStatus.ACTIVE
        channel.is_active = True
        channel.save(update_fields=("status", "is_active", "updated_at"))
    return credential


@transaction.atomic
def set_manual_amazon_credentials(channel, payload, partial=False):
    if channel.platform.code != "amazon":
        raise serializers.ValidationError({"channel": "Channel is not an Amazon channel."})
    credential = set_channel_credentials(channel, payload, partial=partial)
    channel.status = ChannelStatus.ACTIVE
    channel.is_active = True
    channel.authorized_at = timezone.now()
    channel.save(update_fields=("status", "is_active", "authorized_at", "updated_at"))
    return credential


def credential_status(channel):
    credential = _existing(channel)
    data = {
        "configured": credential is not None,
        "platform": channel.platform.code,
        "credential_status": "configured" if credential else "not_configured",
        "updated_at": credential.updated_at if credential else None,
    }
    if credential and channel.platform.code == "woocommerce":
        data["store_url"] = credential.store_url
        data["verify_ssl"] = credential.verify_ssl
    return data
