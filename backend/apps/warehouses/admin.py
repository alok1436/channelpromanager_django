from django.contrib import admin

from .models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "company", "city", "country")
    list_filter = ("country", "customer", "company")
    search_fields = ("name", "customer__email", "company__name", "email", "city")
    readonly_fields = ("created_at", "updated_at")
