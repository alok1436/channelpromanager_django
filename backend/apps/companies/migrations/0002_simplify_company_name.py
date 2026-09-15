from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("companies", "0001_initial")]

    operations = [
        migrations.RemoveConstraint(
            model_name="company",
            name="unique_active_company_short_name_per_customer",
        ),
        migrations.RenameField(
            model_name="company",
            old_name="complete_name",
            new_name="name",
        ),
        migrations.RemoveField(
            model_name="company",
            name="short_name",
        ),
        migrations.AlterModelOptions(
            name="company",
            options={"ordering": ("name",)},
        ),
        migrations.AddConstraint(
            model_name="company",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=("customer", "name"),
                name="unique_active_company_name_per_customer",
            ),
        ),
    ]
