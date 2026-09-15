import re

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from apps.products.models import ProductTranslation


LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")


def normalize_language_code(value):
    parts = value.strip().replace("_", "-").split("-", 1)
    normalized = parts[0].lower() + (f"-{parts[1].upper()}" if len(parts) == 2 else "")
    if not LANGUAGE_PATTERN.fullmatch(normalized):
        raise serializers.ValidationError("Use a language code such as en, de, en-GB, or de-DE.")
    supported = {code.lower() for code in settings.PRODUCT_SUPPORTED_LANGUAGES}
    if supported and normalized.lower() not in supported and normalized.split("-", 1)[0] not in supported:
        raise serializers.ValidationError(f"Language {normalized} is not enabled for product content.")
    return normalized


def validate_bullet_points(value):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise serializers.ValidationError("Bullet points must be a list of non-empty text values.")
    return [item.strip() for item in value]


@transaction.atomic
def create_translation(product, values):
    code = normalize_language_code(values["language_code"])
    if ProductTranslation.objects.filter(product=product, language_code__iexact=code).exists():
        raise serializers.ValidationError({"language_code": "This language already exists for the product."})
    values["language_code"] = code
    return ProductTranslation.objects.create(customer=product.customer, product=product, **values)


@transaction.atomic
def update_translation(translation, values):
    if "language_code" in values:
        code = normalize_language_code(values["language_code"])
        if ProductTranslation.objects.filter(product=translation.product, language_code__iexact=code).exclude(pk=translation.pk).exists():
            raise serializers.ValidationError({"language_code": "This language already exists for the product."})
        values["language_code"] = code
    for field, value in values.items():
        setattr(translation, field, value)
    translation.save()
    return translation
