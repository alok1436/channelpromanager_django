import apps.platforms.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("platforms", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="platform",
            name="logo",
            field=models.ImageField(blank=True, upload_to=apps.platforms.models.platform_logo_path),
        ),
    ]
