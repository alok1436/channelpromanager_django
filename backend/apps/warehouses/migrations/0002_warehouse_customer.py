import django.db.models.deletion
from django.db import migrations, models


def copy_company_customer(apps, schema_editor):
    Warehouse = apps.get_model("warehouses", "Warehouse")
    for warehouse in Warehouse.objects.select_related("company").iterator():
        warehouse.customer_id = warehouse.company.customer_id
        warehouse.save(update_fields=("customer",))


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0005_remove_customer_roles_delete_customerrole"),
        ("warehouses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="warehouse",
            name="customer",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="warehouses",
                to="customers.customer",
            ),
        ),
        migrations.RunPython(copy_company_customer, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="warehouse",
            name="unique_warehouse_name_per_company",
        ),
        migrations.RemoveIndex(
            model_name="warehouse",
            name="warehouses__company_d983b6_idx",
        ),
        migrations.RemoveField(model_name="warehouse", name="company"),
        migrations.AlterField(
            model_name="warehouse",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="warehouses",
                to="customers.customer",
            ),
        ),
        migrations.AddConstraint(
            model_name="warehouse",
            constraint=models.UniqueConstraint(
                fields=("customer", "name"),
                name="unique_warehouse_name_per_customer",
            ),
        ),
        migrations.AddIndex(
            model_name="warehouse",
            index=models.Index(fields=("customer", "name"), name="warehouses_customer_name_idx"),
        ),
    ]

