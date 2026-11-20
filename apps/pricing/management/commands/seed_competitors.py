from django.core.management.base import BaseCommand

from apps.pricing.models import Competitor

COMPETITORS = [
    ("Agilus Diagnostics", "https://www.agilusdiagnostics.com"),
    ("Dr Lal PathLabs", "https://www.lalpathlabs.com"),
    ("Metropolis Healthcare", "https://www.metropolisindia.com"),
    ("PathCare Labs", ""),
]

# Competitors to delete if they still exist - removing one here drops its prices
# too (CASCADE). Redcliffe Labs was dropped from the partner panel.
REMOVE_COMPETITORS = ["Redcliffe Labs"]


class Command(BaseCommand):
    help = "Seed the partner labs (idempotent). Prices are entered manually by Admins."

    def handle(self, *args, **options):
        for order, (name, site) in enumerate(COMPETITORS, start=1):
            obj, created = Competitor.objects.get_or_create(name=name, defaults={"website": site, "display_order": order})
            self.stdout.write(f"{'Created' if created else 'Exists '}: {obj}")
        for name in REMOVE_COMPETITORS:
            deleted, _ = Competitor.objects.filter(name=name).delete()
            if deleted:
                self.stdout.write(f"Removed  : {name}")
