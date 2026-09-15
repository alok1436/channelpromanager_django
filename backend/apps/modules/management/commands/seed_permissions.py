from django.core.management.base import BaseCommand
from django.db import transaction

from apps.modules.models import Module
from apps.permissions.models import Permission


MODULE_ACTIONS = {
    "Dashboard": ("view",),
    "Customers": ("view", "create", "update", "delete"),
    "Companies": ("view", "create", "update", "delete"),
    "Channels": ("view", "create", "update", "delete", "credentials", "authorize"),
    "Orders": ("view", "create", "update", "delete", "cancel"),
    "Products": ("view", "create", "update", "delete", "import", "export"),
    "Inventory": ("view", "adjust"),
    "Warehouses": ("view", "create", "update", "delete"),
    "Shipments": ("view", "create", "update"),
    "Reports": ("view", "export"),
    "Marketplaces": ("view", "manage"),
    "Staff": ("view", "create", "update", "delete"),
    "Roles": ("view", "create", "update", "delete"),
    "Settings": ("view", "update"),
    "Integrations": ("view", "manage"),
}


@transaction.atomic
def seed():
    for position, (name, actions) in enumerate(MODULE_ACTIONS.items()):
        slug = name.lower()
        module, _ = Module.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "sort_order": position, "is_active": True},
        )
        for action in actions:
            Permission.objects.update_or_create(
                codename=f"{slug}.{action}",
                defaults={"module": module, "name": f"{action.title()} {name}", "is_active": True},
            )


class Command(BaseCommand):
    help = "Idempotently seed multi-tenant modules and permissions."

    def handle(self, *args, **options):
        seed()
        self.stdout.write(self.style.SUCCESS("Default modules and permissions seeded."))
