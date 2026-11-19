"""Seeds the public site's content scaffolding.

Only the *structure* is seeded - health concerns and medicine aisles, which are
the same everywhere - and only where it does not already exist, so running this
again never overwrites what the lab has edited. Nothing here invents a fact the
lab has to stand behind: no opening hours, no phone number, no licence number,
no doctor. Those are filled in from /system-admin/ and the site hides each
block until they are.

The health concern -> test mapping is clinical, so every concern is wired to
tests by name and whatever is missing is simply left unlinked and reported.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.patients.models import TestCatalog
from apps.public.models import HealthConcern, MedicineCategory

CONCERNS = [
    ("Full Body Checkup", "grid_view", "The routine panel most doctors start with.",
     ["Complete Blood Count", "Lipid Profile", "Liver Function Test", "Kidney Function Test",
      "Blood Sugar Fasting", "Thyroid Profile"]),
    ("Diabetes", "water_drop", "Sugar control, now and over the last three months.",
     ["Blood Sugar Fasting", "Blood Sugar Postprandial", "HbA1c", "Kidney Function Test"]),
    ("Thyroid", "autorenew", "Tiredness, weight change, hair fall.",
     ["Thyroid Profile", "TSH", "T3", "T4"]),
    ("Fever", "warning", "Fever that has lasted more than two days.",
     ["Complete Blood Count", "Malaria Parasite", "Widal Test", "Dengue NS1", "Typhoid"]),
    ("Heart", "trending_up", "Cholesterol and cardiac risk.",
     ["Lipid Profile", "ECG", "Troponin I", "Blood Sugar Fasting"]),
    ("Vitamins", "celebration", "Vitamin D and B12, the two most often low here.",
     ["Vitamin D", "Vitamin B12", "Calcium", "Iron Studies"]),
    ("Liver & Kidney", "science", "Function tests for both organs.",
     ["Liver Function Test", "Kidney Function Test", "Uric Acid", "Serum Creatinine"]),
    ("Women's Health", "groups", "Anaemia, thyroid and hormones.",
     ["Complete Blood Count", "Thyroid Profile", "Iron Studies", "Vitamin D"]),
]

MEDICINE_CATEGORIES = [
    ("Prescription Medicines", "medication", "Dispensed against a valid prescription only.", True,
     "Antibiotics\nBlood pressure medicines\nDiabetes medicines\nThyroid medicines"),
    ("Diabetes Care", "water_drop", "Strips, lancets, glucometers and diabetes medicines.", False,
     "Glucometers and test strips\nLancets\nInsulin syringes\nSugar-free sweeteners"),
    ("Pain & Fever", "medical_services", "Everyday relief, over the counter.", False,
     "Paracetamol\nPain relief sprays and gels\nCrepe bandages\nHot and cold packs"),
    ("Vitamins & Supplements", "celebration", "Vitamin, calcium and iron supplements.", False,
     "Vitamin D sachets\nVitamin B-complex\nCalcium tablets\nIron and folic acid\nProtein powders"),
    ("Baby & Mother Care", "groups", "For newborns and new mothers.", False,
     "Infant formula\nDiapers and wipes\nBaby oil and lotion\nFeeding bottles"),
    ("Devices & Monitors", "stethoscope", "Measure at home between visits.", False,
     "Blood pressure monitors\nThermometers\nNebulisers\nPulse oximeters\nWeighing scales"),
    ("First Aid", "shield", "The box every house should have.", False,
     "Antiseptic liquid\nCotton and gauze\nAdhesive bandages\nSurgical tape"),
]


class Command(BaseCommand):
    help = "Create the public site's health concerns and medicine categories (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        made_concerns = linked = 0
        unmatched = []

        for order, (name, icon, blurb, test_names) in enumerate(CONCERNS, start=1):
            concern, created = HealthConcern.objects.get_or_create(
                name=name, defaults={"icon": icon, "blurb": blurb, "display_order": order}
            )
            made_concerns += int(created)
            if not created:
                continue
            for test_name in test_names:
                # `name__iexact` first, then a contains match: the seeded
                # catalogue spells some tests differently ("TSH" vs
                # "Thyroid Stimulating Hormone"), and a near miss is better
                # than a silently empty concern page.
                test = (
                    TestCatalog.objects.filter(name__iexact=test_name).first()
                    or TestCatalog.objects.filter(name__icontains=test_name).first()
                )
                if test:
                    concern.tests.add(test)
                    linked += 1
                else:
                    unmatched.append(f"{name}: {test_name}")

        made_categories = 0
        for order, (name, icon, blurb, needs_rx, examples) in enumerate(MEDICINE_CATEGORIES, start=1):
            _, created = MedicineCategory.objects.get_or_create(
                name=name,
                defaults={
                    "icon": icon, "blurb": blurb, "needs_prescription": needs_rx,
                    "examples": examples, "display_order": order,
                },
            )
            made_categories += int(created)

        self.stdout.write(
            f"seed_public_content: {made_concerns} health concerns (+{linked} test links), "
            f"{made_categories} medicine categories"
        )
        if unmatched:
            self.stdout.write(self.style.WARNING(
                f"  {len(unmatched)} test name(s) not in the catalogue, left unlinked: "
                + "; ".join(unmatched[:8]) + ("; ..." if len(unmatched) > 8 else "")
            ))
        self.stdout.write(
            "  Nothing else is seeded. Fill in the centre photos, opening hours, phone numbers "
            "and the pharmacy licence from /system-admin/ - the public pages hide each block until you do."
        )
