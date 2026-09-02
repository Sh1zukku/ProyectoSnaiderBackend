from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Shipment


class Command(BaseCommand):
    help = "Elimina shipments cargados hace 10 días o más"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=10)

        deleted_count, _ = Shipment.objects.filter(
            created_at__lte=cutoff
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Se eliminaron {deleted_count} registros relacionados."
            )
        )
