import django.db.models.deletion
from django.db import migrations, models


def assign_customer_company(apps, schema_editor):
    Warehouse = apps.get_model("warehouses", "Warehouse")
    Company = apps.get_model("companies", "Company")

    for warehouse in Warehouse.objects.filter(company__isnull=True).iterator():
        company = Company.objects.filter(
            customer_id=warehouse.customer_id,
            is_active=True,
            deleted_at__isnull=True,
        ).order_by("created_at", "id").first()
        if company:
            warehouse.company_id = company.id
            warehouse.save(update_fields=("company",))


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0002_simplify_company_name"),
        ("warehouses", "0002_warehouse_customer"),
    ]

    operations = [
        migrations.AddField(
            model_name="warehouse",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="warehouses",
                to="companies.company",
            ),
        ),
        migrations.RunPython(assign_customer_company, migrations.RunPython.noop),
    ]

