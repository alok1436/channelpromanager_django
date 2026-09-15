from copy import copy

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.companies.models import Company
from apps.products.models import Product, ProductImage, ProductStatus, ProductTranslation, ProductVariant, ProductVariantAttribute


def normalize_sku(value):
    return value.strip().upper()


def validate_company(customer, company):
    if company is not None and (company.customer_id != customer.id or not company.is_active or company.deleted_at is not None):
        raise serializers.ValidationError({"company_id": "Select an active company belonging to your customer."})


def validate_unique_product_sku(customer, sku, instance=None):
    queryset = Product.objects.filter(customer=customer, sku__iexact=sku)
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        raise serializers.ValidationError({"sku": "A product with this SKU already exists."})


@transaction.atomic
def create_product(*, customer, user, translations=None, variants=None, **values):
    values.pop("customer", None)
    values.pop("created_by", None)
    values.pop("updated_by", None)
    values["sku"] = normalize_sku(values["sku"])
    validate_company(customer, values.get("company"))
    validate_unique_product_sku(customer, values["sku"])
    product = Product.objects.create(customer=customer, created_by=user, updated_by=user, **values)
    for translation in translations or []:
        ProductTranslation.objects.create(customer=customer, product=product, **translation)
    for variant in variants or []:
        attributes = variant.pop("attributes", [])
        variant["sku"] = normalize_sku(variant["sku"])
        created = ProductVariant.objects.create(customer=customer, product=product, **variant)
        ProductVariantAttribute.objects.bulk_create([
            ProductVariantAttribute(variant=created, position=index, **attribute)
            for index, attribute in enumerate(attributes)
        ])
    return product


@transaction.atomic
def update_product(product, *, user, **values):
    values.pop("customer", None)
    values.pop("created_by", None)
    if "sku" in values:
        values["sku"] = normalize_sku(values["sku"])
        validate_unique_product_sku(product.customer, values["sku"], product)
    if "company" in values:
        validate_company(product.customer, values["company"])
    for field, value in values.items():
        setattr(product, field, value)
    product.updated_by = user
    product.save()
    return product


@transaction.atomic
def archive_product(product, user):
    product.status = ProductStatus.ARCHIVED
    product.is_active = False
    product.updated_by = user
    product.save(update_fields=("status", "is_active", "updated_by", "updated_at"))
    return product


@transaction.atomic
def restore_product(product, user):
    product.status = ProductStatus.DRAFT
    product.is_active = True
    product.updated_by = user
    product.save(update_fields=("status", "is_active", "updated_by", "updated_at"))
    return product


def _copy_sku(customer, source_sku):
    base = f"{source_sku}-COPY"
    candidate = base
    suffix = 2
    while Product.objects.filter(customer=customer, sku=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


@transaction.atomic
def duplicate_product(product, user):
    duplicate = copy(product)
    duplicate.pk = None
    duplicate.sku = _copy_sku(product.customer, product.sku)
    duplicate.status = ProductStatus.DRAFT
    duplicate.is_active = True
    duplicate.created_by = user
    duplicate.updated_by = user
    duplicate.save()
    ProductTranslation.objects.bulk_create([
        ProductTranslation(
            customer=product.customer, product=duplicate, language_code=item.language_code,
            name=item.name, short_description=item.short_description, description=item.description,
            bullet_points=item.bullet_points, meta_title=item.meta_title, meta_description=item.meta_description,
        ) for item in product.translations.all()
    ])
    ProductImage.objects.bulk_create([
        ProductImage(customer=product.customer, product=duplicate, image=item.image.name, alt_text=item.alt_text, position=item.position, is_primary=item.is_primary)
        for item in product.images.all()
    ])
    for variant in product.variants.prefetch_related("attributes"):
        new_variant = ProductVariant.objects.create(
            customer=product.customer, product=duplicate, sku=_copy_variant_sku(product.customer, variant.sku),
            ean=variant.ean, upc=variant.upc, gtin=variant.gtin, mpn=variant.mpn,
            purchase_price=variant.purchase_price, standard_sale_price=variant.standard_sale_price,
            weight=variant.weight, is_active=variant.is_active,
        )
        ProductVariantAttribute.objects.bulk_create([
            ProductVariantAttribute(variant=new_variant, name=attribute.name, value=attribute.value, position=attribute.position)
            for attribute in variant.attributes.all()
        ])
    return duplicate


def _copy_variant_sku(customer, source_sku):
    base = f"{source_sku}-COPY"
    candidate = base
    suffix = 2
    while ProductVariant.objects.filter(customer=customer, sku=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


@transaction.atomic
def bulk_status(customer, product_ids, status, user):
    unique_ids = set(product_ids)
    products = list(Product.objects.select_for_update().filter(customer=customer, id__in=unique_ids))
    if len(products) != len(unique_ids):
        raise serializers.ValidationError({"product_ids": "One or more products do not belong to your customer."})
    active = status != ProductStatus.ARCHIVED
    Product.objects.filter(pk__in=unique_ids).update(status=status, is_active=active, updated_by=user, updated_at=timezone.now())
    return len(products)
