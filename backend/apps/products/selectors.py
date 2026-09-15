from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404

from .models import Product, ProductImage, ProductTranslation, ProductVariant


def product_list_for_customer(customer):
    return Product.objects.filter(customer=customer).select_related("company").annotate(
        variant_count=Count("variants", distinct=True)
    ).prefetch_related(
        Prefetch("translations", queryset=ProductTranslation.objects.order_by("language_code"), to_attr="prefetched_translations"),
        Prefetch("images", queryset=ProductImage.objects.filter(is_primary=True).order_by("position"), to_attr="prefetched_primary_images"),
    )


def product_detail_for_customer(customer):
    return Product.objects.filter(customer=customer).select_related("company", "created_by", "updated_by").prefetch_related(
        Prefetch("translations", queryset=ProductTranslation.objects.order_by("language_code")),
        Prefetch("images", queryset=ProductImage.objects.order_by("position", "id")),
        Prefetch("variants", queryset=ProductVariant.objects.prefetch_related("attributes").order_by("sku")),
    )


def get_customer_product(*, customer, product_id):
    return get_object_or_404(product_detail_for_customer(customer), pk=product_id)
