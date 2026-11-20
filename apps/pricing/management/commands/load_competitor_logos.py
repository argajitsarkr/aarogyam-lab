from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.pricing.models import Competitor

# Maps each seeded competitor to its logo in static/img/partners/. The source
# files ship in the repo; this command copies them onto the model's ImageField
# (which writes to the media volume), so the public test pages can show them.
LOGOS = {
    "Agilus Diagnostics": "agilus.png",
    "Dr Lal PathLabs": "lal-pathlabs.jpg",
    "Metropolis Healthcare": "metropolis.png",
    "PathCare Labs": "pathcare.png",
}


class Command(BaseCommand):
    help = "Load the partner-lab logos from static/img/partners/ onto each Competitor (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace a logo even if the competitor already has one.",
        )

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR) / "static" / "img" / "partners"
        for name, filename in LOGOS.items():
            try:
                competitor = Competitor.objects.get(name=name)
            except Competitor.DoesNotExist:
                self.stdout.write(f"Skip (no competitor): {name}")
                continue
            if competitor.logo and not options["force"]:
                self.stdout.write(f"Has logo : {name}")
                continue
            source = base / filename
            if not source.exists():
                self.stdout.write(f"Missing  : {source}")
                continue
            with source.open("rb") as fh:
                competitor.logo.save(filename, File(fh), save=True)
            self.stdout.write(f"Loaded   : {name} <- {filename}")
