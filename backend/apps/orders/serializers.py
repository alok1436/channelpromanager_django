from rest_framework import serializers
from apps.customers.models import Customer
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id", "external_item_id", "product", "sku", "asin", "title",
            "quantity_ordered", "quantity_shipped", "item_price", "item_tax",
            "shipping_price", "shipping_tax", "promotion_discount", "currency",
            "condition_id", "condition_subtype_id",
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Customer.objects.filter(is_active=True), write_only=True, required=False)
    items = OrderItemSerializer(many=True, read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and not request.user.is_superuser:
            fields.pop("customer_id", None)
        return fields

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "external_order_id", "seller_order_id", "customer", "customer_id",
            "channel", "marketplace", "status", "external_status", "fulfillment_channel", "sales_channel",
            "ship_service_level", "total", "currency", "number_of_items_shipped", "number_of_items_unshipped",
            "buyer_email", "buyer_name", "shipping_address", "purchase_date", "last_update_date",
            "earliest_ship_date", "latest_ship_date", "imported_at", "items", "created_at", "updated_at",
        )
        read_only_fields = (
            "external_order_id", "seller_order_id", "channel", "marketplace", "external_status", "fulfillment_channel",
            "sales_channel", "ship_service_level", "number_of_items_shipped", "number_of_items_unshipped", "buyer_email",
            "buyer_name", "shipping_address", "purchase_date", "last_update_date", "earliest_ship_date", "latest_ship_date",
            "imported_at", "created_at", "updated_at",
        )
