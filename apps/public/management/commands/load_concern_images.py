from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.public.models import HealthConcern

# Maps each seeded health concern to its tile image in static/img/concerns/.
# The files ship in the repo; this copies them onto the model's ImageField
# (which writes to the media volume), so the home-page tiles show a photo
# instead of the fallback icon.
IMAGES = {
    "Fever": "fever.png",
    "Thyroid": "thyroid.png",
    "Full Body Checkup": "full-body-checkup.png",
}


class Command(BaseCommand):
    help = "Load the health-concern tile images from static/img/concerns/ (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Replace an image even if the concern already has one.",
        )

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR) / "static" / "img" / "concerns"
        for name, filename in IMAGES.items():
            try:
                concern = HealthConcern.objects.get(name=name)
            except HealthConcern.DoesNotExist:
                self.stdout.write(f"Skip (no concern): {name}")
                continue
            if concern.image and not options["force"]:
                self.stdout.write(f"Has image: {name}")
                continue
            source = base / filename
            if not source.exists():
                self.stdout.write(f"Missing  : {source}")
                continue
            with source.open("rb") as fh:
                concern.image.save(filename, File(fh), save=True)
            self.stdout.write(f"Loaded   : {name} <- {filename}")
