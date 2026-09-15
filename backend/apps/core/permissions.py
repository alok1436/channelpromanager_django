from rest_framework.permissions import BasePermission

def effective_permission_codenames(user):
    if not user or not user.is_authenticated: return set()
    if user.is_superuser:
        from apps.permissions.models import Permission
        return set(Permission.objects.filter(is_active=True, module__is_active=True).values_list("codename", flat=True))
    from apps.customers.services import effective_customer_permissions, get_customer_membership
    membership = get_customer_membership(user)
    if membership is None: return set()
    if membership.is_owner:
        from apps.permissions.models import Permission
        return set(Permission.objects.filter(is_active=True, module__is_active=True).values_list("codename", flat=True))
    return set(effective_customer_permissions(user, membership))

class HasModulePermission(BasePermission):
    message = "You do not have the required module permission."
    action_map = {"list": "view", "retrieve": "view", "create": "create", "update": "update", "partial_update": "update", "destroy": "delete"}
    def has_permission(self, request, view):
        if not request.user.is_authenticated: return False
        if request.user.is_superuser: return True
        required = getattr(view, "required_permission", None)
        if required is None:
            module = getattr(view, "permission_module", None)
            action = self.action_map.get(getattr(view, "action", None))
            required = f"{module}.{action}" if module and action else None
        return bool(required and required in effective_permission_codenames(request.user))

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_superuser)
