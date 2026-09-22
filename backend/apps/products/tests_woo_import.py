import base64
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.channels.models import Channel
from apps.companies.models import Company
from apps.customers.models import Customer, CustomerMembership
from apps.platforms.models import Platform
from apps.products.models import Product, ProductStock, ProductVariant, WooProductImport
from apps.products.services.woo_import import import_woo_csv
from apps.users.models import User
from apps.warehouses.models import Warehouse


CSV_DATA = ("ID,Tipo,SKU,Nome,Breve descrizione,Descrizione,Pubblicato,Magazzino,Prezzo di listino,Prezzo in offerta,Genitore,Nome dell'attributo 1,Valore dell'attributo 1\n"
            "10,variable,SHIRT,Camicia,Breve testo,Descrizione italiana,1,8,20,,,Color,Blue\n"
            "11,variation,SHIRT-BLUE,Camicia blu,,,1,3,22,18,SHIRT,Color,Blue\n")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="woo-import-tests-"), CHANNEL_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"0" * 32).decode())
class WooImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platforms", verbosity=0)
        user = User.objects.create_user("woo-owner@example.com", "StrongPass123!")
        customer = Customer.objects.create(user=user, first_name="Woo", last_name="Owner", email="woo@example.com")
        CustomerMembership.objects.create(customer=customer, user=user, is_owner=True)
        company = Company.objects.create(customer=customer, name="Woo Company")
        cls.user = user
        cls.channel = Channel.objects.create(customer=customer, company=company, platform=Platform.objects.get(code="woocommerce"), name="Woo", country_code="DE")
        cls.warehouse = Warehouse.objects.create(customer=customer, company=company, name="Main")

    def test_csv_import_is_idempotent_and_links_variation_and_stock(self):
        job = WooProductImport.objects.create(
            customer=self.channel.customer, channel=self.channel, warehouse=self.warehouse, uploaded_by=self.user,
            source_file=SimpleUploadedFile("woo.csv", CSV_DATA.encode()), language_code="it",
        )
        import_woo_csv(job)
        import_woo_csv(job)
        product = Product.objects.get(customer=self.channel.customer, sku="SHIRT")
        variant = ProductVariant.objects.get(customer=self.channel.customer, sku="SHIRT-BLUE")
        self.assertEqual(variant.product, product)
        translation = product.translations.get(language_code="it")
        self.assertEqual(translation.name, "Camicia")
        self.assertEqual(translation.short_description, "Breve testo")
        self.assertEqual(translation.description, "Descrizione italiana")
        self.assertFalse(product.translations.filter(language_code="en").exists())
        self.assertEqual(ProductStock.objects.get(product=product, variant__isnull=True).quantity, 8)
        self.assertEqual(ProductStock.objects.get(variant=variant).quantity, 3)
        self.assertEqual(Product.objects.filter(customer=self.channel.customer).count(), 1)
        self.assertEqual(ProductVariant.objects.filter(customer=self.channel.customer).count(), 1)

    def test_out_of_range_stock_does_not_fail_import(self):
        csv_data = CSV_DATA.replace('Descrizione italiana,1,8,', 'Descrizione italiana,1,48011353306338,')
        job = WooProductImport.objects.create(
            customer=self.channel.customer, channel=self.channel, warehouse=self.warehouse, uploaded_by=self.user,
            source_file=SimpleUploadedFile('woo.csv', csv_data.encode()), language_code='en',
        )

        import_woo_csv(job)

        self.assertEqual(job.status, WooProductImport.Status.COMPLETED)
        self.assertEqual(ProductStock.objects.get(product__sku='SHIRT', variant__isnull=True).quantity, 0)

    @patch("apps.products.tasks.import_woo_products.delay")
    def test_upload_endpoint_queues_job_and_status_is_available(self, delay):
        client = APIClient()
        client.force_authenticate(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(
                f"/api/v1/channels/{self.channel.id}/woo-product-import/",
                {"warehouse_id": self.warehouse.id, "language_code": "it", "file": SimpleUploadedFile("woo.csv", CSV_DATA.encode())},
                format="multipart",
            )
        self.assertEqual(response.status_code, 202, response.data)
        delay.assert_called_once_with(response.data["id"])
        detail = client.get(f"/api/v1/channels/{self.channel.id}/woo-product-import/{response.data['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["status"], "queued")
        self.assertEqual(WooProductImport.objects.get(pk=response.data["id"]).language_code, "it")
