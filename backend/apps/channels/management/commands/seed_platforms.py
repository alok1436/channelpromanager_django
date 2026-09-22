from django.core.management.base import BaseCommand

from apps.platforms.models import Platform


PLATFORMS = (
    ("Amazon", "amazon", "Everything from A to Z."),
    ("eBay", "ebay", "Buy it, sell it, love it."),
    ("Cdiscount", "cdiscount", "French ecommerce made accessible."),
    ("WooCommerce", "woocommerce", "Commerce built on WordPress."),
    ("Otto", "otto", "A trusted home for modern retail."),
    ("Kaufland", "kaufland", "One marketplace, millions of customers."),
)


class Command(BaseCommand):
    help = "Idempotently seed supported channel platforms."

    def handle(self, *args, **options):
        for name, code, description in PLATFORMS:
            Platform.objects.update_or_create(
                code=code,
                defaults={"name": name, "description": description, "is_active": True},
            )
        self.stdout.write(self.style.SUCCESS("Channel platforms seeded."))
