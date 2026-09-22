from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "channel", "external_status", "total", "currency", "purchase_date")
    list_filter = ("status", "external_status", "fulfillment_channel", "channel")
    search_fields = ("order_number", "external_order_id", "buyer_email")
    inlines = (OrderItemInline,)
