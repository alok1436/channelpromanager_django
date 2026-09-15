from django.db import migrations


def remove_legacy_role(apps, schema_editor):
    Role = apps.get_model("roles", "Role")
    CustomerRole = apps.get_model("customers", "CustomerRole")
    roles = Role.objects.filter(slug="super-admin", customer_id=None)
    CustomerRole.objects.filter(role__in=roles).delete()
    roles.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0004_backfill_owner_memberships"),
        ("roles", "0002_role_customer_alter_role_name_alter_role_slug_and_more"),
    ]
    operations = [migrations.RunPython(remove_legacy_role, migrations.RunPython.noop)]
