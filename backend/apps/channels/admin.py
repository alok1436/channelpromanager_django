from django.contrib import admin

from .models import Channel, ChannelMarketplace, Marketplace


class ChannelMarketplaceInline(admin.TabularInline):
    model = ChannelMarketplace
    extra = 0
    readonly_fields = (
        "last_orders_sync_at", "last_listing_sync_at", "last_inventory_sync_at",
        "last_price_sync_at", "created_at", "updated_at",
    )


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "company", "platform", "country_code", "status", "is_active")
    list_filter = ("platform", "country_code", "status", "is_active")
    search_fields = ("name", "customer__email", "company__name", "vat")
    readonly_fields = ("created_by", "updated_by", "authorized_at", "last_sync_at", "created_at", "updated_at")
    inlines = (ChannelMarketplaceInline,)


@admin.register(Marketplace)
class MarketplaceAdmin(admin.ModelAdmin):
    list_display = ("name", "platform", "country_code", "currency_code", "external_marketplace_id", "is_active")
    list_filter = ("platform", "country_code", "region", "is_active")
    search_fields = ("name", "code", "external_marketplace_id")
    readonly_fields = ("created_at", "updated_at")

