from rest_framework import serializers

from apps.channels.models import CustomerAmazonSetting, CustomerEbaySetting
from .encryption import decrypt_secret, encrypt_secret


SECRET_FIELDS = {
    "amazon": {"lwa_client_id", "lwa_client_secret", "spapi_application_id"},
    "ebay": {"client_id", "client_secret", "redirect_uri"},
}
MODEL_BY_PROVIDER = {"amazon": CustomerAmazonSetting, "ebay": CustomerEbaySetting}
REQUIRED_FIELDS = {
    "amazon": SECRET_FIELDS["amazon"] | {"oauth_callback_url"},
    "ebay": SECRET_FIELDS["ebay"] | {"oauth_callback_url"},
}


def get_provider_setting(customer, provider):
    model = MODEL_BY_PROVIDER[provider]
    setting = model.objects.filter(customer=customer, is_active=True).first()
    if setting is None:
        raise serializers.ValidationError({provider: f"Configure {provider.title()} credentials in Channel Settings before authorizing a channel."})
    return setting


def decrypted_provider_setting(customer, provider):
    setting = get_provider_setting(customer, provider)
    return setting, {field: decrypt_secret(getattr(setting, field)) for field in SECRET_FIELDS[provider]}


def save_provider_setting(customer, provider, values):
    model = MODEL_BY_PROVIDER[provider]
    current = model.objects.filter(customer=customer).first()
    encrypted = {}
    for key, value in values.items():
        if key in SECRET_FIELDS[provider]:
            if value:
                encrypted[key] = encrypt_secret(value)
        else:
            encrypted[key] = value
    required = REQUIRED_FIELDS[provider]
    if current is None:
        missing = sorted(field for field in required if not encrypted.get(field))
        if missing:
            raise serializers.ValidationError({provider: f"Required fields: {', '.join(missing)}"})
    setting, _ = model.objects.update_or_create(customer=customer, defaults=encrypted)
    return setting
