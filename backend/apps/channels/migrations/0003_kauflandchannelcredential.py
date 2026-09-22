import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("channels", "0002_customeramazonsetting_customerebaysetting")]

    operations = [
        migrations.CreateModel(
            name="KauflandChannelCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client_key", models.TextField()),
                ("client_secret", models.TextField()),
                ("channel", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="kaufland_credentials", to="channels.channel")),
            ],
        ),
    ]
