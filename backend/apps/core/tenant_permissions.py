from rest_framework.permissions import BasePermission

from apps.customers.services import get_customer_membership, has_customer_permission


class CustomerModulePermission(BasePermission):
    action_map = {
        "list": "view", "retrieve": "view", "create": "create",
        "update": "update", "partial_update": "update", "destroy": "delete",
    }
    message = "You do not have permission for this customer action."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        membership = get_customer_membership(request.user)
        if membership is None:
            return False
        view.customer_membership = membership
        view.current_customer = membership.customer
        action = self.action_map.get(getattr(view, "action", None))
        permission_map = getattr(view, "permission_map", {})
        code = permission_map.get(getattr(view, "action", None))
        if code is None:
            module = getattr(view, "permission_module", None)
            code = f"{module}.{action}" if module and action else None
        return bool(code and has_customer_permission(request.user, membership.customer, code))
