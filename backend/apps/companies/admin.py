from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "city", "country", "is_active")
    list_filter = ("is_active", "country")
    search_fields = ("name", "email", "customer__email")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
