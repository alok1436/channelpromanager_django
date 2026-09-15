from django.contrib import admin

from .models import Product, ProductImage, ProductTranslation, ProductVariant, ProductVariantAttribute


class ProductTranslationInline(admin.TabularInline):
    model = ProductTranslation
    extra = 0


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "customer", "company", "brand", "condition", "status", "is_active", "updated_at")
    list_filter = ("customer", "company", "status", "condition", "is_active")
    search_fields = ("sku", "ean", "upc", "gtin", "mpn", "brand", "manufacturer", "translations__name")
    autocomplete_fields = ("customer", "company", "created_by", "updated_by")
    inlines = (ProductTranslationInline, ProductImageInline, ProductVariantInline)


@admin.register(ProductTranslation)
class ProductTranslationAdmin(admin.ModelAdmin):
    list_display = ("product", "language_code", "name", "customer", "updated_at")
    list_filter = ("customer", "language_code")
    search_fields = ("product__sku", "name")


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "position", "is_primary", "customer")
    list_filter = ("customer", "is_primary")
    search_fields = ("product__sku", "alt_text")


class ProductVariantAttributeInline(admin.TabularInline):
    model = ProductVariantAttribute
    extra = 0


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "customer", "standard_sale_price", "is_active")
    list_filter = ("customer", "is_active")
    search_fields = ("sku", "ean", "upc", "gtin", "mpn", "product__sku")
    inlines = (ProductVariantAttributeInline,)


@admin.register(ProductVariantAttribute)
class ProductVariantAttributeAdmin(admin.ModelAdmin):
    list_display = ("variant", "name", "value", "position")
    search_fields = ("variant__sku", "name", "value")
