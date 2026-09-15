from django.contrib import admin

from .models import Role, RolePermission


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_system_role", "is_active")
    search_fields = ("name", "slug")
    list_filter = ("is_system_role", "is_active")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "created_at")
    autocomplete_fields = ("role", "permission")
