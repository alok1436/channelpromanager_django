from django.core.management.base import BaseCommand
from django.db import transaction

from apps.channels.models import Marketplace
from apps.platforms.models import Platform


MARKETPLACES = {
    "amazon": (
        ("Amazon Germany", "amazon_de", "DE", "EUR", "A1PA6795UKMFR9", "eu"),
        ("Amazon Italy", "amazon_it", "IT", "EUR", "APJ6JRA9NG5V4", "eu"),
        ("Amazon France", "amazon_fr", "FR", "EUR", "A13V1IB3VIYZZH", "eu"),
        ("Amazon Spain", "amazon_es", "ES", "EUR", "A1RKKUPIHCS9HS", "eu"),
        ("Amazon UK", "amazon_uk", "GB", "GBP", "A1F83G8C2ARO7P", "eu"),
        ("Amazon Netherlands", "amazon_nl", "NL", "EUR", "A1805IZSGTT6HS", "eu"),
        ("Amazon Belgium", "amazon_be", "BE", "EUR", "AMEN7PMS3EDWL", "eu"),
    ),
    "ebay": (
        ("eBay Germany", "ebay_de", "DE", "EUR", "EBAY_DE", "eu"),
        ("eBay Italy", "ebay_it", "IT", "EUR", "EBAY_IT", "eu"),
        ("eBay France", "ebay_fr", "FR", "EUR", "EBAY_FR", "eu"),
        ("eBay Spain", "ebay_es", "ES", "EUR", "EBAY_ES", "eu"),
        ("eBay UK", "ebay_uk", "GB", "GBP", "EBAY_GB", "eu"),
        ("eBay Netherlands", "ebay_nl", "NL", "EUR", "EBAY_NL", "eu"),
        ("eBay Belgium", "ebay_be", "BE", "EUR", "EBAY_BE", "eu"),
    ),
}


class Command(BaseCommand):
    help = "Idempotently seed supported Amazon and eBay marketplaces."

    @transaction.atomic
    def handle(self, *args, **options):
        for platform_code, rows in MARKETPLACES.items():
            platform = Platform.objects.get(code=platform_code)
            for name, code, country, currency, external_id, region in rows:
                Marketplace.objects.update_or_create(
                    code=code,
                    defaults={
                        "platform": platform,
                        "name": name,
                        "country_code": country,
                        "currency_code": currency,
                        "external_marketplace_id": external_id,
                        "region": region,
                        "is_active": True,
                    },
                )
        self.stdout.write(self.style.SUCCESS("Channel marketplaces seeded."))

