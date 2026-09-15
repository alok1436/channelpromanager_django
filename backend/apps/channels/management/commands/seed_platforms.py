from django.core.management.base import BaseCommand

from apps.platforms.models import Platform


PLATFORMS = (
    ("Amazon", "amazon"),
    ("eBay", "ebay"),
    ("Cdiscount", "cdiscount"),
    ("WooCommerce", "woocommerce"),
    ("Otto", "otto"),
)


class Command(BaseCommand):
    help = "Idempotently seed supported channel platforms."

    def handle(self, *args, **options):
        for name, code in PLATFORMS:
            Platform.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})
        self.stdout.write(self.style.SUCCESS("Channel platforms seeded."))

