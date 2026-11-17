from django.core.management.base import BaseCommand

from apps.pricing.models import Competitor

COMPETITORS = [
    ("Agilus Diagnostics", "https://www.agilusdiagnostics.com"),
    ("Redcliffe Labs", "https://redcliffelabs.com"),
    ("Dr Lal PathLabs", "https://www.lalpathlabs.com"),
    ("Metropolis Healthcare", "https://www.metropolisindia.com"),
    ("PathCare Labs", ""),
]


class Command(BaseCommand):
    help = "Seed the five initial competitor labs (idempotent). Prices are entered manually by Admins."

    def handle(self, *args, **options):
        for order, (name, site) in enumerate(COMPETITORS, start=1):
            obj, created = Competitor.objects.get_or_create(name=name, defaults={"website": site, "display_order": order})
            self.stdout.write(f"{'Created' if created else 'Exists '}: {obj}")
