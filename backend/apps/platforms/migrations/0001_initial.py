from django.db import migrations, models


def seed_platforms(apps, schema_editor):
    Platform = apps.get_model("platforms", "Platform")
    for name, code in (
        ("Amazon", "amazon"),
        ("eBay", "ebay"),
        ("Otto", "otto"),
        ("Cdiscount", "cdiscount"),
        ("WooCommerce", "woocommerce"),
    ):
        Platform.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Platform",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150)),
                ("code", models.CharField(db_index=True, max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                ("logo_url", models.URLField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.RunPython(seed_platforms, migrations.RunPython.noop),
    ]

