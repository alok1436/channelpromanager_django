from django.contrib import admin

from .models import Platform


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at")

