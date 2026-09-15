from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


def product_image_path(instance, filename):
    return f"products/customer_{instance.customer_id}/product_{instance.product_id}/{filename}"


class ProductStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    DISCONTINUED = "discontinued", "Discontinued"
    ARCHIVED = "archived", "Archived"


class ProductCondition(models.TextChoices):
    NEW = "new", "New"
    USED = "used", "Used"
    REFURBISHED = "refurbished", "Refurbished"


class Product(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="products")
    company = models.ForeignKey("companies.Company", null=True, blank=True, on_delete=models.PROTECT, related_name="products")
    sku = models.CharField(max_length=150)
    brand = models.CharField(max_length=150, blank=True)
    manufacturer = models.CharField(max_length=150, blank=True)
    mpn = models.CharField(max_length=150, blank=True)
    ean = models.CharField(max_length=50, blank=True)
    upc = models.CharField(max_length=50, blank=True)
    isbn = models.CharField(max_length=50, blank=True)
    gtin = models.CharField(max_length=50, blank=True)
    product_type = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=50, choices=ProductCondition.choices, default=ProductCondition.NEW, db_index=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    standard_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, blank=True)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, blank=True)
    length = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    dimension_unit = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=30, choices=ProductStatus.choices, default=ProductStatus.DRAFT, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="products_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="products_updated")

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(fields=("customer", "sku"), name="unique_product_sku_per_customer"),
            models.CheckConstraint(condition=Q(purchase_price__gte=0) | Q(purchase_price__isnull=True), name="product_purchase_price_nonnegative"),
            models.CheckConstraint(condition=Q(standard_sale_price__gte=0) | Q(standard_sale_price__isnull=True), name="product_sale_price_nonnegative"),
            models.CheckConstraint(condition=Q(tax_rate__gte=0, tax_rate__lte=100) | Q(tax_rate__isnull=True), name="product_tax_rate_range"),
            models.CheckConstraint(condition=Q(weight__gte=0) | Q(weight__isnull=True), name="product_weight_nonnegative"),
            models.CheckConstraint(condition=Q(length__gte=0) | Q(length__isnull=True), name="product_length_nonnegative"),
            models.CheckConstraint(condition=Q(width__gte=0) | Q(width__isnull=True), name="product_width_nonnegative"),
            models.CheckConstraint(condition=Q(height__gte=0) | Q(height__isnull=True), name="product_height_nonnegative"),
        ]
        indexes = [
            models.Index(fields=("customer", "status"), name="product_customer_status_idx"),
            models.Index(fields=("customer", "is_active"), name="product_customer_active_idx"),
            models.Index(fields=("customer", "company"), name="product_customer_company_idx"),
            models.Index(fields=("customer", "brand"), name="product_customer_brand_idx"),
        ]

    def clean(self):
        if self.company_id and self.customer_id and self.company.customer_id != self.customer_id:
            raise ValidationError({"company": "Company must belong to the product customer."})

    def save(self, *args, **kwargs):
        self.sku = self.sku.strip().upper()
        self.currency_code = self.currency_code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sku


class ProductTranslation(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="product_translations")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="translations")
    language_code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    bullet_points = models.JSONField(default=list, blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("language_code",)
        constraints = [models.UniqueConstraint(fields=("product", "language_code"), name="unique_product_translation_language")]
        indexes = [models.Index(fields=("customer", "language_code"), name="prod_trans_customer_lang_idx")]

    def clean(self):
        if self.product_id and self.customer_id and self.product.customer_id != self.customer_id:
            raise ValidationError({"customer": "Translation customer must match its product."})

    def __str__(self):
        return f"{self.product.sku} ({self.language_code})"


class ProductImage(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="product_images")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to=product_image_path)
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("product",), condition=Q(is_primary=True), name="unique_primary_image_per_product"),
        ]
        indexes = [models.Index(fields=("customer", "product", "position"), name="prod_img_customer_order_idx")]

    def clean(self):
        if self.product_id and self.customer_id and self.product.customer_id != self.customer_id:
            raise ValidationError({"customer": "Image customer must match its product."})


class ProductVariant(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="product_variants")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=150)
    ean = models.CharField(max_length=50, blank=True)
    upc = models.CharField(max_length=50, blank=True)
    gtin = models.CharField(max_length=50, blank=True)
    mpn = models.CharField(max_length=150, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    standard_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("sku",)
        constraints = [
            models.UniqueConstraint(fields=("customer", "sku"), name="unique_variant_sku_per_customer"),
            models.CheckConstraint(condition=Q(purchase_price__gte=0) | Q(purchase_price__isnull=True), name="variant_purchase_price_nonnegative"),
            models.CheckConstraint(condition=Q(standard_sale_price__gte=0) | Q(standard_sale_price__isnull=True), name="variant_sale_price_nonnegative"),
            models.CheckConstraint(condition=Q(weight__gte=0) | Q(weight__isnull=True), name="variant_weight_nonnegative"),
        ]
        indexes = [models.Index(fields=("customer", "product", "is_active"), name="product_variant_customer_idx")]

    def clean(self):
        if self.product_id and self.customer_id and self.product.customer_id != self.customer_id:
            raise ValidationError({"customer": "Variant customer must match its product."})

    def save(self, *args, **kwargs):
        self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sku


class ProductVariantAttribute(TimeStampedModel):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=("variant", "name"), name="unique_attribute_name_per_variant")]

    def __str__(self):
        return f"{self.name}: {self.value}"
