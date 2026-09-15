from django.db import transaction
from rest_framework import serializers

from apps.products.models import ProductVariant, ProductVariantAttribute
from .product_service import normalize_sku


def validate_unique_variant_sku(customer, sku, instance=None):
    queryset = ProductVariant.objects.filter(customer=customer, sku__iexact=sku)
    if instance:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        raise serializers.ValidationError({"sku": "A variant with this SKU already exists."})


def _replace_attributes(variant, attributes):
    names = [attribute["name"].strip().lower() for attribute in attributes]
    if len(names) != len(set(names)):
        raise serializers.ValidationError({"attributes": "Attribute names must be unique within a variant."})
    variant.attributes.all().delete()
    ProductVariantAttribute.objects.bulk_create([
        ProductVariantAttribute(variant=variant, name=attribute["name"].strip(), value=attribute["value"].strip(), position=index)
        for index, attribute in enumerate(attributes)
    ])


@transaction.atomic
def create_variant(product, values):
    attributes = values.pop("attributes", [])
    values["sku"] = normalize_sku(values["sku"])
    validate_unique_variant_sku(product.customer, values["sku"])
    variant = ProductVariant.objects.create(customer=product.customer, product=product, **values)
    _replace_attributes(variant, attributes)
    return variant


@transaction.atomic
def update_variant(variant, values):
    attributes = values.pop("attributes", None)
    if "sku" in values:
        values["sku"] = normalize_sku(values["sku"])
        validate_unique_variant_sku(variant.customer, values["sku"], variant)
    for field, value in values.items():
        setattr(variant, field, value)
    variant.save()
    if attributes is not None:
        _replace_attributes(variant, attributes)
    return variant
