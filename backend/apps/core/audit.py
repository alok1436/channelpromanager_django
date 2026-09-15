from .models import AuditLog
SENSITIVE = {"password", "token", "access", "refresh", "secret", "consumer_key", "client_id"}
def _clean_value(values):
    if isinstance(values, dict):
        return {
            k: _clean_value(v)
            for k, v in values.items()
            if not any(marker in k.lower() for marker in SENSITIVE)
        }
    if isinstance(values, (list, tuple)):
        return [_clean_value(value) for value in values]
    return values
def clean_values(values):
    return _clean_value(values or {})
def record_audit(request, action, instance, old_values=None, new_values=None):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    AuditLog.objects.create(user=request.user if request.user.is_authenticated else None, action=action, module=instance._meta.app_label, object_type=instance._meta.label, object_id=str(instance.pk), old_values=clean_values(old_values), new_values=clean_values(new_values), ip_address=forwarded or request.META.get("REMOTE_ADDR"))
