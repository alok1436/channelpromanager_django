from celery import shared_task

from apps.products.models import WooProductImport
from apps.products.services.woo_import import import_woo_csv


@shared_task(autoretry_for=(Exception,), retry_backoff=60, retry_kwargs={"max_retries": 2})
def import_woo_products(import_id):
    import_job = WooProductImport.objects.select_related("customer", "channel__company", "warehouse").get(pk=import_id)
    import_woo_csv(import_job)
    return {"imported": import_job.imported, "skipped": import_job.skipped}
