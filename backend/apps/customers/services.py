from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied

from .models import CustomerMembership


def get_customer_membership(user, customer=None):
    if not user or not user.is_authenticated or user.is_superuser:
        return None
    queryset = CustomerMembership.objects.filter(user=user, is_active=True, customer__is_active=True).select_related("customer", "role")
    if customer is not None:
        queryset = queryset.filter(customer=customer)
    return queryset.order_by("-is_owner", "created_at").first()


def get_current_customer(user):
    membership = get_customer_membership(user)
    if membership is None:
        raise PermissionDenied("An active customer membership is required.")
    return membership.customer


def has_customer_permission(user, customer, permission_code):
    if user.is_superuser:
        return True
    membership = get_customer_membership(user, customer)
    if membership is None:
        return False
    if membership.is_owner:
        return True
    if not membership.role_id or not membership.role.is_active:
        return False
    return membership.role.permissions.filter(
        codename=permission_code,
        is_active=True,
        module__is_active=True,
    ).exists()


def effective_customer_permissions(user, membership):
    if user.is_superuser or membership is None or membership.is_owner:
        return []
    if not membership.role_id:
        return []
    return list(membership.role.permissions.filter(is_active=True, module__is_active=True).values_list("codename", flat=True).distinct().order_by("codename"))
