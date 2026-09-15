from django.db import migrations


def backfill_owner_memberships(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    CustomerMembership = apps.get_model("customers", "CustomerMembership")
    for customer in Customer.objects.exclude(user_id=None).select_related("user"):
        if customer.user.is_superuser:
            customer.user_id = None
            customer.save(update_fields=("user",))
            continue
        CustomerMembership.objects.get_or_create(
            customer=customer,
            user=customer.user,
            defaults={"is_owner": True, "is_active": customer.is_active},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0003_customermembership"),
        ("roles", "0002_role_customer_alter_role_name_alter_role_slug_and_more"),
    ]
    operations = [migrations.RunPython(backfill_owner_memberships, migrations.RunPython.noop)]
