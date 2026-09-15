from django.db import transaction
from rest_framework import serializers

from apps.products.models import ProductImage


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def validate_image_file(image):
    if image.size > 10 * 1024 * 1024:
        raise serializers.ValidationError("Image must be 10 MB or smaller.")
    if getattr(image, "content_type", None) not in ALLOWED_IMAGE_TYPES:
        raise serializers.ValidationError("Upload a JPEG, PNG, WebP, or GIF image.")
    return image


@transaction.atomic
def create_image(product, values):
    image = validate_image_file(values["image"])
    existing = ProductImage.objects.select_for_update().filter(product=product)
    make_primary = values.get("is_primary", False) or not existing.exists()
    if make_primary:
        existing.update(is_primary=False)
    position = values.get("position")
    if position is None:
        last = existing.order_by("-position").first()
        position = (last.position + 1) if last else 0
    return ProductImage.objects.create(
        customer=product.customer, product=product, image=image,
        alt_text=values.get("alt_text", ""), position=position, is_primary=make_primary,
    )


@transaction.atomic
def update_image(image, values):
    if values.get("is_primary"):
        ProductImage.objects.select_for_update().filter(product=image.product, is_primary=True).exclude(pk=image.pk).update(is_primary=False)
    for field, value in values.items():
        setattr(image, field, value)
    image.save()
    return image


@transaction.atomic
def delete_image(image):
    product = image.product
    was_primary = image.is_primary
    image.delete()
    if was_primary:
        replacement = ProductImage.objects.filter(product=product).order_by("position", "id").first()
        if replacement:
            replacement.is_primary = True
            replacement.save(update_fields=("is_primary", "updated_at"))


@transaction.atomic
def reorder_images(product, image_ids):
    ids = list(image_ids)
    if len(ids) != len(set(ids)):
        raise serializers.ValidationError({"image_ids": "Image IDs must be unique."})
    images = list(ProductImage.objects.select_for_update().filter(product=product, id__in=ids))
    existing_ids = set(ProductImage.objects.filter(product=product).values_list("id", flat=True))
    if set(ids) != existing_ids:
        raise serializers.ValidationError({"image_ids": "Provide every image for this product exactly once."})
    by_id = {image.id: image for image in images}
    for position, image_id in enumerate(ids):
        image = by_id[image_id]
        image.position = position
    ProductImage.objects.bulk_update(images, ("position",))
    return sorted(images, key=lambda item: item.position)
