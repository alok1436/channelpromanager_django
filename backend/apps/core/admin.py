from django.contrib import admin
from .models import AuditLog
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "object_type", "object_id"); readonly_fields = tuple(f.name for f in AuditLog._meta.fields)
