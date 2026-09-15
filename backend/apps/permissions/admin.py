from django.contrib import admin

from .models import Permission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "name", "module", "is_active")
    search_fields = ("codename", "name")
    list_filter = ("module", "is_active")
