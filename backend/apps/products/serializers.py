from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.companies.models import Company
from apps.customers.services import get_current_customer
from apps.products.models import (
    Product, ProductCondition, ProductImage, ProductStatus, ProductTranslation,
    ProductVariant, ProductVariantAttribute,
)
from apps.products.services.image_service import validate_image_file
from apps.products.services.product_service import create_product, normalize_sku, update_product, validate_company, validate_unique_product_sku
from apps.products.services.translation_service import normalize_language_code, validate_bullet_points
from apps.products.services.variant_service import validate_unique_variant_sku


class ProductCompanySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ProductTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTranslation
        fields = (
            "id", "language_code", "name", "short_description", "description",
            "bullet_points", "meta_title", "meta_description", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        validators = []

    def validate_language_code(self, value):
        return normalize_language_code(value)

    def validate_bullet_points(self, value):
        return validate_bullet_points(value)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Product name is required.")
        return value


class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariantAttribute
        fields = ("id", "name", "value", "position")
        read_only_fields = ("id", "position")
        validators = []

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Attribute name is required.")
        return value.strip()

    def validate_value(self, value):
        if not value.strip():
            raise serializers.ValidationError("Attribute value is required.")
        return value.strip()


class ProductVariantSerializer(serializers.ModelSerializer):
    attributes = ProductVariantAttributeSerializer(many=True, required=False)

    class Meta:
        model = ProductVariant
        fields = (
            "id", "sku", "ean", "upc", "gtin", "mpn", "purchase_price",
            "standard_sale_price", "weight", "is_active", "attributes", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        validators = []
        extra_kwargs = {
            "purchase_price": {"min_value": Decimal("0")},
            "standard_sale_price": {"min_value": Decimal("0")},
            "weight": {"min_value": Decimal("0")},
        }

    def validate_sku(self, value):
        return normalize_sku(value)

    def validate(self, attrs):
        attributes = attrs.get("attributes")
        if attributes is not None:
            names = [item["name"].lower() for item in attributes]
            if len(names) != len(set(names)):
                raise serializers.ValidationError({"attributes": "Attribute names must be unique."})
        return attrs


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "image", "image_url", "alt_text", "position", "is_primary", "created_at", "updated_at")
        read_only_fields = ("id", "image_url", "created_at", "updated_at")
        extra_kwargs = {"image": {"write_only": True}}

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, image):
        if not image.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url

    def validate_image(self, value):
        return validate_image_file(value)


PRODUCT_FIELDS = (
    "company", "sku", "brand", "manufacturer", "mpn", "ean", "upc", "isbn", "gtin",
    "product_type", "condition", "purchase_price", "standard_sale_price", "currency_code",
    "tax_rate", "weight", "weight_unit", "length", "width", "height", "dimension_unit",
    "status", "is_active",
)


class ProductWriteMixin:
    def validate_sku(self, value):
        return normalize_sku(value)

    def validate_currency_code(self, value):
        return value.strip().upper()

    def validate_identifier(self, value, label):
        value = value.strip().replace(" ", "").replace("-", "")
        if value and (not value.isdigit() or not 6 <= len(value) <= 14):
            raise serializers.ValidationError(f"{label} must contain 6 to 14 digits.")
        return value

    def validate_ean(self, value):
        return self.validate_identifier(value, "EAN")

    def validate_upc(self, value):
        return self.validate_identifier(value, "UPC")

    def validate_gtin(self, value):
        return self.validate_identifier(value, "GTIN")

    def validate(self, attrs):
        request = self.context["request"]
        customer = get_current_customer(request.user)
        if any(field in self.initial_data for field in ("customer", "customer_id", "created_by", "updated_by")):
            raise serializers.ValidationError({"customer_id": "Tenant and audit ownership are assigned by the server."})
        company = attrs.get("company", getattr(self.instance, "company", None))
        validate_company(customer, company)
        sku = attrs.get("sku", getattr(self.instance, "sku", None))
        if sku:
            validate_unique_product_sku(customer, sku, self.instance)
        for field in ("purchase_price", "standard_sale_price", "weight", "length", "width", "height"):
            if attrs.get(field) is not None and attrs[field] < 0:
                raise serializers.ValidationError({field: "Value cannot be negative."})
        if attrs.get("tax_rate") is not None and not Decimal("0") <= attrs["tax_rate"] <= Decimal("100"):
            raise serializers.ValidationError({"tax_rate": "Tax rate must be between 0 and 100."})
        return attrs


class ProductCreateSerializer(ProductWriteMixin, serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), required=False, allow_null=True)
    translations = ProductTranslationSerializer(many=True)
    variants = ProductVariantSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ("company_id",) + PRODUCT_FIELDS[1:] + ("translations", "variants")
        validators = []
        extra_kwargs = {
            "purchase_price": {"min_value": Decimal("0")}, "standard_sale_price": {"min_value": Decimal("0")},
            "tax_rate": {"min_value": Decimal("0"), "max_value": Decimal("100")},
            "weight": {"min_value": Decimal("0")}, "length": {"min_value": Decimal("0")},
            "width": {"min_value": Decimal("0")}, "height": {"min_value": Decimal("0")},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        translations = attrs.get("translations", [])
        languages = [item["language_code"].lower() for item in translations]
        if not translations:
            raise serializers.ValidationError({"translations": "At least one product translation is required."})
        if len(languages) != len(set(languages)):
            raise serializers.ValidationError({"translations": "Each language may only appear once."})
        customer = get_current_customer(self.context["request"].user)
        seen_variant_skus = set()
        for variant in attrs.get("variants", []):
            sku = variant["sku"]
            if sku in seen_variant_skus:
                raise serializers.ValidationError({"variants": f"Duplicate variant SKU: {sku}"})
            validate_unique_variant_sku(customer, sku)
            seen_variant_skus.add(sku)
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return create_product(customer=get_current_customer(request.user), user=request.user, **validated_data)


class ProductUpdateSerializer(ProductWriteMixin, serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Product
        fields = ("company_id",) + PRODUCT_FIELDS[1:]
        validators = []

    def update(self, instance, validated_data):
        return update_product(instance, user=self.context["request"].user, **validated_data)


def _localized_name(product, language):
    translations = product.prefetched_translations if hasattr(product, "prefetched_translations") else list(product.translations.all())
    if not translations:
        return ""
    requested = (language or "").replace("_", "-").lower()
    base = requested.split("-", 1)[0]
    by_code = {item.language_code.lower(): item.name for item in translations}
    return by_code.get(requested) or by_code.get(base) or by_code.get("en") or translations[0].name


class ProductListSerializer(serializers.ModelSerializer):
    company = ProductCompanySummarySerializer(read_only=True)
    name = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    variant_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "sku", "name", "brand", "company", "ean", "standard_sale_price",
            "currency_code", "status", "is_active", "primary_image", "variant_count", "created_at", "updated_at",
        )

    @extend_schema_field(serializers.CharField())
    def get_name(self, product):
        return _localized_name(product, self.context.get("language"))

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_primary_image(self, product):
        images = getattr(product, "prefetched_primary_images", [])
        if not images:
            return None
        request = self.context.get("request")
        url = images[0].image.url
        return request.build_absolute_uri(url) if request else url


class ProductDetailSerializer(serializers.ModelSerializer):
    company = ProductCompanySummarySerializer(read_only=True)
    translations = ProductTranslationSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "company") + PRODUCT_FIELDS[1:] + (
            "translations", "images", "variants", "created_at", "updated_at",
        )


class ImageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("alt_text", "position", "is_primary")


class ImageReorderSerializer(serializers.Serializer):
    image_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)


class BulkStatusSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    status = serializers.ChoiceField(choices=ProductStatus.choices)


class BulkArchiveSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
