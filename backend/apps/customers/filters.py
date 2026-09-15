import django_filters
from .models import Customer
class CustomerFilter(django_filters.FilterSet):
    role = django_filters.NumberFilter(field_name="roles__id")
    class Meta: model = Customer; fields = ("company", "role", "is_active")
