from django.core.management.base import BaseCommand

from apps.retest.services import generate_candidates


class Command(BaseCommand):
    help = "Run the re-test candidate generator now (normally run daily by Celery beat)."

    def add_arguments(self, parser):
        parser.add_argument("--lookahead", type=int, default=None)

    def handle(self, *args, **opts):
        n = generate_candidates(lookahead_days=opts["lookahead"])
        self.stdout.write(self.style.SUCCESS(f"Created {n} re-test candidates."))
