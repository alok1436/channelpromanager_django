from rest_framework import serializers
from apps.customers.models import Customer
from .models import Order
class OrderSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Customer.objects.filter(is_active=True), write_only=True, required=False)
    class Meta: model = Order; fields = ("id", "order_number", "customer", "customer_id", "status", "total", "currency", "created_at", "updated_at"); read_only_fields = ("created_at", "updated_at")
