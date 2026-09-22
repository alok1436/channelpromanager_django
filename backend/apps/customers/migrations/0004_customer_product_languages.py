from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("customers", "0003_customermembership")]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="product_languages",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
