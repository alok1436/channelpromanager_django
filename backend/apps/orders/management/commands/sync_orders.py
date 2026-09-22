from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.channels.models import Channel
from apps.orders.services import get_order_service


class Command(BaseCommand):
    help = "Download orders and items for one configured sales channel."

    def add_arguments(self, parser):
        parser.add_argument("channel_id", type=int)
        parser.add_argument("--updated-after", help="Optional ISO-8601 timestamp; defaults to the channel sync cursor or 14 days ago.")

    def handle(self, *args, **options):
        try:
            channel = Channel.objects.select_related("platform", "customer").get(pk=options["channel_id"], is_active=True)
        except Channel.DoesNotExist as exc:
            raise CommandError("Active channel not found.") from exc
        updated_after = parse_datetime(options["updated_after"]) if options["updated_after"] else None
        if options["updated_after"] and updated_after is None:
            raise CommandError("--updated-after must be a valid ISO-8601 timestamp.")
        result = get_order_service(channel).download_orders(updated_after=updated_after)
        self.stdout.write(self.style.SUCCESS(str(result.as_dict())))
