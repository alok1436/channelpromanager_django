from django.db import models

from apps.core.models import TimeStampedModel


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="orders")
    channel = models.ForeignKey("channels.Channel", null=True, blank=True, on_delete=models.PROTECT, related_name="orders")
    marketplace = models.ForeignKey("channels.Marketplace", null=True, blank=True, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=100, db_index=True)
    external_order_id = models.CharField(max_length=150, blank=True, db_index=True)
    seller_order_id = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    external_status = models.CharField(max_length=50, blank=True, db_index=True)
    fulfillment_channel = models.CharField(max_length=30, blank=True)
    sales_channel = models.CharField(max_length=100, blank=True)
    ship_service_level = models.CharField(max_length=100, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    number_of_items_shipped = models.PositiveIntegerField(default=0)
    number_of_items_unshipped = models.PositiveIntegerField(default=0)
    buyer_email = models.EmailField(blank=True)
    buyer_name = models.CharField(max_length=255, blank=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    purchase_date = models.DateTimeField(null=True, blank=True, db_index=True)
    last_update_date = models.DateTimeField(null=True, blank=True)
    earliest_ship_date = models.DateTimeField(null=True, blank=True)
    latest_ship_date = models.DateTimeField(null=True, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-purchase_date", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("channel", "external_order_id"),
                condition=models.Q(channel__isnull=False) & ~models.Q(external_order_id=""),
                name="unique_external_order_per_channel",
            )
        ]
        indexes = [models.Index(fields=("customer", "channel", "status"), name="order_cust_chan_status_idx")]

    def __str__(self):
        return self.order_number


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items")
    external_item_id = models.CharField(max_length=150)
    sku = models.CharField(max_length=150, blank=True, db_index=True)
    asin = models.CharField(max_length=20, blank=True, db_index=True)
    title = models.CharField(max_length=500, blank=True)
    quantity_ordered = models.PositiveIntegerField(default=0)
    quantity_shipped = models.PositiveIntegerField(default=0)
    item_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    item_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    promotion_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, blank=True)
    condition_id = models.CharField(max_length=50, blank=True)
    condition_subtype_id = models.CharField(max_length=50, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("id",)
        constraints = [models.UniqueConstraint(fields=("order", "external_item_id"), name="unique_external_item_per_order")]
        indexes = [models.Index(fields=("order", "sku"), name="order_item_order_sku_idx")]

    def __str__(self):
        return f"{self.order.order_number}: {self.sku or self.external_item_id}"
