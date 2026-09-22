"""WooCommerce CSV importer. No Woo API credentials are needed for this workflow."""

import csv
import re
from decimal import Decimal, InvalidOperation
from html import unescape

from django.db import transaction
from django.utils import timezone

from apps.products.models import (
    Product, ProductStatus, ProductStock, ProductTranslation,
    ProductVariant, ProductVariantAttribute, WooProductImport,
)


def _text(value):
    return unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def _number(value):
    try:
        return Decimal(str(value or "").strip().replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def _quantity(value):
    number = _number(value)
    # Django's PositiveIntegerField uses a signed 32-bit PostgreSQL integer.
    # Some Woo exports contain an identifier or otherwise corrupt stock value.
    if number is None or not 0 <= number <= 2_147_483_647:
        return 0
    return int(number)


def _row_sku(row):
    sku = (row.get("SKU") or "").strip().upper()
    woo_id = (row.get("ID") or "").strip()
    return (sku or (f"WOO-{woo_id}" if woo_id else ""))[:150]


def _attributes(row):
    result = []
    for index in range(1, 6):
        name = (row.get(f"Nome dell'attributo {index}") or "").strip()
        value = (row.get(f"Valore dell'attributo {index}") or "").strip()
        if name and value:
            result.append((name[:100], value[:255]))
    return result


def _product_values(row, company):
    regular = _number(row.get("Prezzo di listino"))
    sale = _number(row.get("Prezzo in offerta"))
    price = sale if sale is not None else regular
    values = {"company": company, "product_type": (row.get("Tipo") or "simple")[:100]}
    values["status"] = ProductStatus.ACTIVE if (row.get("Pubblicato") or "").strip() == "1" else ProductStatus.INACTIVE
    values["is_active"] = values["status"] == ProductStatus.ACTIVE
    if price is not None and price >= 0:
        values["standard_sale_price"] = price
        values["currency_code"] = "EUR"
    ean = (row.get("GTIN13 / EAN") or row.get("GTIN, UPC, EAN, o ISBN") or "").strip()
    values["ean"] = ean[:50]
    values["mpn"] = (row.get("MPN") or "").strip()[:150]
    for source, target in (("Peso (kg)", "weight"), ("Lunghezza (cm)", "length"), ("Larghezza (cm)", "width"), ("Altezza (cm)", "height")):
        number = _number(row.get(source))
        if number is not None and number >= 0:
            values[target] = number
    values["weight_unit"] = "kg"
    values["dimension_unit"] = "cm"
    return values


@transaction.atomic
def _save_parent(import_job, row, sku):
    customer = import_job.customer
    defaults = _product_values(row, import_job.channel.company)
    product, _ = Product.objects.update_or_create(customer=customer, sku=sku, defaults=defaults)
    name = _text(row.get("Nome")) or sku
    description = _text(row.get("Descrizione")) or _text(row.get("Breve descrizione"))
    ProductTranslation.objects.update_or_create(
        product=product, language_code=import_job.language_code,
        defaults={"customer": customer, "name": name[:255], "short_description": _text(row.get("Breve descrizione")), "description": description},
    )
    ProductStock.objects.update_or_create(
        product=product, variant=None, warehouse=import_job.warehouse,
        defaults={"quantity": _quantity(row.get("Magazzino"))},
    )
    return product


@transaction.atomic
def _save_variant(import_job, row, sku, parent):
    price = _number(row.get("Prezzo in offerta"))
    if price is None:
        price = _number(row.get("Prezzo di listino"))
    defaults = {"product": parent, "is_active": (row.get("Pubblicato") or "").strip() == "1"}
    if price is not None and price >= 0:
        defaults["standard_sale_price"] = price
    variant, _ = ProductVariant.objects.update_or_create(customer=import_job.customer, sku=sku, defaults=defaults)
    for position, (name, value) in enumerate(_attributes(row)):
        ProductVariantAttribute.objects.update_or_create(
            variant=variant, name=name, defaults={"value": value, "position": position},
        )
    ProductStock.objects.update_or_create(
        product=parent, variant=variant, warehouse=import_job.warehouse,
        defaults={"quantity": _quantity(row.get("Magazzino"))},
    )


def import_woo_csv(import_job):
    """Stream a WooCommerce export; safely retryable through SKU-scoped upserts."""
    import_job.status = WooProductImport.Status.RUNNING
    import_job.error = ""
    import_job.save(update_fields=("status", "error", "updated_at"))
    imported = skipped = platform_products = 0
    try:
        with import_job.source_file.open("rb") as source:
            reader = csv.DictReader((line.decode("utf-8-sig") for line in source))
            if not reader.fieldnames or not {"Tipo", "SKU", "Nome"}.issubset(reader.fieldnames):
                raise ValueError("CSV must contain Tipo, SKU, and Nome headings.")
            parents = {}
            variations = []
            for row in reader:
                if None in row:
                    raise ValueError("CSV row has more values than headings.")
                sku = _row_sku(row)
                if not sku:
                    skipped += 1
                    continue
                if (row.get("Tipo") or "").strip().lower() == "variation":
                    variations.append((row, sku))
                    continue
                product = _save_parent(import_job, row, sku)
                parents[sku] = product
                woo_id = (row.get("ID") or "").strip()
                if woo_id:
                    parents[woo_id] = product
                imported += 1
                platform_products += 1
            for row, sku in variations:
                reference = (row.get("Genitore") or "").strip()
                parent = parents.get(reference.upper()) or parents.get(reference.removeprefix("id:"))
                if parent is None:
                    skipped += 1
                    continue
                _save_variant(import_job, row, sku, parent)
                imported += 1
        import_job.imported = imported
        import_job.platform_products = platform_products
        import_job.skipped = skipped
        import_job.status = WooProductImport.Status.COMPLETED
        import_job.completed_at = timezone.now()
        import_job.save(update_fields=("imported", "platform_products", "skipped", "status", "completed_at", "updated_at"))
    except Exception:
        import_job.status = WooProductImport.Status.FAILED
        import_job.error = "Import failed. Check the CSV format and server logs."
        import_job.save(update_fields=("status", "error", "updated_at"))
        raise
    return import_job
