import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("channels", "0002_customeramazonsetting_customerebaysetting"),
        ("orders", "0002_alter_order_options"),
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(name="order", options={"ordering": ("-purchase_date", "-created_at")}),
        migrations.AlterField(model_name="order", field=models.CharField(db_index=True, max_length=100), name="order_number"),
        migrations.AlterField(model_name="order", field=models.DecimalField(decimal_places=2, default=0, max_digits=14), name="total"),
        migrations.AddField(model_name="order", name="channel", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="channels.channel")),
        migrations.AddField(model_name="order", name="marketplace", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="channels.marketplace")),
        migrations.AddField(model_name="order", name="external_order_id", field=models.CharField(blank=True, db_index=True, max_length=150)),
        migrations.AddField(model_name="order", name="seller_order_id", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="order", name="external_status", field=models.CharField(blank=True, db_index=True, max_length=50)),
        migrations.AddField(model_name="order", name="fulfillment_channel", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="order", name="sales_channel", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="order", name="ship_service_level", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="order", name="number_of_items_shipped", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="order", name="number_of_items_unshipped", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="order", name="buyer_email", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="order", name="buyer_name", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="order", name="shipping_address", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="order", name="purchase_date", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="order", name="last_update_date", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="order", name="earliest_ship_date", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="order", name="latest_ship_date", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="order", name="imported_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="order", name="raw_data", field=models.JSONField(blank=True, default=dict)),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("external_item_id", models.CharField(max_length=150)), ("sku", models.CharField(blank=True, db_index=True, max_length=150)),
                ("asin", models.CharField(blank=True, db_index=True, max_length=20)), ("title", models.CharField(blank=True, max_length=500)),
                ("quantity_ordered", models.PositiveIntegerField(default=0)), ("quantity_shipped", models.PositiveIntegerField(default=0)),
                ("item_price", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("item_tax", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("shipping_price", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("shipping_tax", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("promotion_discount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("currency", models.CharField(blank=True, max_length=3)), ("condition_id", models.CharField(blank=True, max_length=50)),
                ("condition_subtype_id", models.CharField(blank=True, max_length=50)), ("raw_data", models.JSONField(blank=True, default=dict)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="products.product")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddConstraint(model_name="order", constraint=models.UniqueConstraint(condition=models.Q(channel__isnull=False) & ~models.Q(external_order_id=""), fields=("channel", "external_order_id"), name="unique_external_order_per_channel")),
        migrations.AddIndex(model_name="order", index=models.Index(fields=["customer", "channel", "status"], name="order_cust_chan_status_idx")),
        migrations.AddConstraint(model_name="orderitem", constraint=models.UniqueConstraint(fields=("order", "external_item_id"), name="unique_external_item_per_order")),
        migrations.AddIndex(model_name="orderitem", index=models.Index(fields=["order", "sku"], name="order_item_order_sku_idx")),
    ]
