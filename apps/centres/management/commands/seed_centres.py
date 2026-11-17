from django.core.management.base import BaseCommand

from apps.centres.models import Centre

CENTRES = [
    {"name": "Aarogyam Pathology", "short_code": "ARP", "locality": "Ram Nagar", "address": "Ram Nagar, Agartala",
     "colour": "#0f766e", "is_head_centre": True},
    {"name": "Radha Rani MediClinic", "short_code": "RRM", "locality": "Border Road", "address": "Border Road, Agartala",
     "colour": "#7c3aed", "is_head_centre": False},
    {"name": "BeHealthy", "short_code": "BHY", "locality": "", "address": "",
     "colour": "#ea580c", "is_head_centre": False},
]


class Command(BaseCommand):
    help = "Seed the three initial centres (idempotent; existing centres are left untouched)."

    def handle(self, *args, **options):
        for data in CENTRES:
            obj, created = Centre.objects.get_or_create(short_code=data["short_code"], defaults=data)
            self.stdout.write(f"{'Created' if created else 'Exists '}: {obj} ({obj.short_code})")
