"""Fake patients, visits, follow-ups and calls across all centres — for testing only.

Refuses to run when DEBUG=False so it can never pollute production data.
"""
import datetime as dt
import random
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.centres.models import Centre
from apps.followups.models import FollowUp
from apps.patients.models import Doctor, Patient, PinCodeLocation, TestCatalog, Visit, VisitTest
from apps.pricing.models import Competitor, CompetitorPrice
from apps.retest.models import CallLog, RetestCandidate
from apps.retest.services import generate_candidates, log_call

FIRST = ["Rina", "Sumit", "Ananya", "Bikash", "Puja", "Rahul", "Moumita", "Sanjib", "Priya", "Abhijit", "Tanushree",
         "Debasish", "Riya", "Partha", "Shreya", "Amit", "Barnali", "Joydeep", "Sudipa", "Ratan"]
LAST = ["Debbarma", "Das", "Saha", "Chakraborty", "Bhattacharjee", "Deb", "Sinha", "Roy", "Paul", "Nath", "Majumder",
        "Reang", "Jamatia", "Tripura", "Datta", "Ghosh"]
# Demo-only approximate points around Agartala (NOT authoritative PIN centroids).
DEMO_LOCALITIES = [
    ("Ram Nagar", "799002", 23.8371, 91.2750), ("Banamalipur", "799001", 23.8335, 91.2830),
    ("Krishnanagar", "799001", 23.8400, 91.2790), ("Dhaleswar", "799007", 23.8250, 91.2950),
    ("Jogendranagar", "799004", 23.8150, 91.3000), ("Abhoynagar", "799005", 23.8480, 91.2950),
    ("Battala", "799001", 23.8290, 91.2760), ("Indranagar", "799006", 23.8560, 91.2990),
    ("Badharghat", "799003", 23.8000, 91.2800), ("Kunjaban", "799006", 23.8550, 91.2870),
]
DEMO_CENTRE_COORDS = {"ARP": (23.8371, 91.2750), "RRM": (23.8210, 91.2680), "BHY": (23.8480, 91.2950)}


class Command(BaseCommand):
    help = "Create fake demo data across all centres (blocked when DEBUG=False)."

    def add_arguments(self, parser):
        parser.add_argument("--patients", type=int, default=150)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("create_demo_data is disabled when DEBUG=False (refusing to add fake data to production).")
        random.seed(opts["seed"])
        call_command("seed_centres", verbosity=0)
        call_command("seed_test_catalog", verbosity=0)
        call_command("seed_competitors", verbosity=0)
        with transaction.atomic():
            self._build(opts["patients"])
        n = generate_candidates()
        self._simulate_calls()
        self.stdout.write(self.style.SUCCESS(f"Demo data ready ({opts['patients']} patients, {n} re-test candidates)."))
        self.stdout.write("Demo logins (password for all: Demo-Pass-2026!): demo_admin, arp_staff1, arp_staff2, rrm_staff1, bhy_staff1")

    def _user(self, username, role, centre=None, first=""):
        user = User.objects.filter(username=username).first()
        if user:
            return user
        user = User(username=username, role=role, home_centre=centre, first_name=first, must_change_password=False,
                    is_staff=role == User.Role.ADMIN, is_superuser=role == User.Role.ADMIN)
        user.set_password("Demo-Pass-2026!")
        user.save()
        return user

    def _build(self, n_patients):
        centres = {c.short_code: c for c in Centre.objects.all()}
        for code, (lat, lng) in DEMO_CENTRE_COORDS.items():
            c = centres.get(code)
            if c and c.latitude is None:
                c.latitude, c.longitude = Decimal(str(lat)), Decimal(str(lng))
                c.save()
        bhy = centres["BHY"]
        if not bhy.address:
            bhy.address, bhy.locality = "Demo address — set by Admin", "Abhoynagar"
            bhy.save()
        for loc, pin, lat, lng in DEMO_LOCALITIES:
            PinCodeLocation.objects.get_or_create(pin_code=pin, defaults={"label": f"{loc} (demo)", "latitude": lat, "longitude": lng})

        self._user("demo_admin", User.Role.ADMIN, first="Demo Admin")
        staff = {
            "ARP": [self._user("arp_staff1", User.Role.EMPLOYEE, centres["ARP"], "Mitali"),
                    self._user("arp_staff2", User.Role.EMPLOYEE, centres["ARP"], "Sourav")],
            "RRM": [self._user("rrm_staff1", User.Role.EMPLOYEE, centres["RRM"], "Pinki")],
            "BHY": [self._user("bhy_staff1", User.Role.EMPLOYEE, centres["BHY"], "Kajal")],
        }
        doctors = [Doctor.objects.get_or_create(name=n, defaults={"clinic": c, "specialty": s, "locality": l})[0] for n, c, s, l in [
            ("S. Debnath", "City Clinic", "General Physician", "Banamalipur"),
            ("R. Saha", "AGMC & GBP Hospital", "Endocrinologist", "Kunjaban"),
            ("P. Chakraborty", "Lifeline Nursing Home", "Cardiologist", "Krishnanagar"),
            ("M. Das", "", "Gynaecologist", "Dhaleswar"),
        ]]
        tests = list(TestCatalog.objects.filter(is_active=True))
        common = [t for t in tests if t.code in ("CBC", "HBA1C", "LIPID", "TSH", "KFT", "LFT", "VITD", "FBS", "URINE", "T3T4")]
        # Competitor prices: ±10–60% around ours
        for comp in Competitor.objects.all():
            for t in tests:
                if random.random() < 0.85:
                    CompetitorPrice.objects.get_or_create(test=t, competitor=comp, defaults={
                        "price": (t.price * Decimal(str(random.uniform(1.0, 1.6)))).quantize(Decimal("1")),
                        "source_note": random.choice(["website", "price list", "phone enquiry"]),
                        "last_verified_on": timezone.localdate() - dt.timedelta(days=random.randint(0, 150))})

        today = timezone.localdate()
        codes = list(centres)
        for i in range(n_patients):
            home = random.choices(codes, weights=[5, 3, 2])[0]
            loc, pin, *_ = random.choice(DEMO_LOCALITIES)
            p = Patient.objects.create(
                full_name=f"{random.choice(FIRST)} {random.choice(LAST)}", sex=random.choice("MF"),
                age_years=random.randint(18, 80), phone=f"{random.choice('6789')}{random.randint(100000000, 999999999)}",
                locality=loc, pin_code=pin, city="Agartala", registered_at_centre=centres[home],
                registered_by=random.choice(staff[home]), consent_to_contact=random.random() < 0.85,
                do_not_call=random.random() < 0.03)
            # 1–4 visits over the past ~10 months, occasionally at another centre
            for _ in range(random.randint(1, 4)):
                c = home if random.random() < 0.85 else random.choice(codes)
                vdate = today - dt.timedelta(days=random.randint(0, 300))
                visit = Visit.objects.create(patient=p, centre=centres[c], visit_date=vdate, registered_by=random.choice(staff[c]),
                                             referring_doctor=random.choice(doctors + [None, None]),
                                             sample_collection_type=random.choice(["CENTRE"] * 4 + ["HOME"]),
                                             payment_mode=random.choice(["CASH", "UPI", "UPI", "CARD"]))
                for t in random.sample(common, random.randint(1, 3)):
                    reported = vdate < today - dt.timedelta(days=1) or random.random() < 0.5
                    VisitTest.objects.create(
                        visit=visit, test=t, price_charged=t.price,
                        result_status="REPORTED" if reported else "PENDING",
                        report_date=vdate + dt.timedelta(days=1) if reported else None,
                        flag=random.choices(["NORMAL", "BORDERLINE", "ABNORMAL"], weights=[7, 2, 1])[0] if reported else "")
                visit.recalculate_total()
                visit.discount = random.choice([0, 0, 0, 50, 100])
                visit.amount_paid = max(visit.total_amount - visit.discount, 0)
                visit.save()
            if random.random() < 0.08:
                FollowUp.objects.create(patient=p, centre=centres[home], reason="DOCTOR_REFERRAL",
                                        referring_doctor=random.choice(doctors), assigned_to=random.choice(staff[home]),
                                        due_date=today + dt.timedelta(days=random.randint(-5, 10)),
                                        priority=random.choice(["HIGH", "MEDIUM", "LOW"]))

    def _simulate_calls(self):
        outcomes = [CallLog.Outcome.NO_ANSWER, CallLog.Outcome.CALL_BACK, CallLog.Outcome.BOOKED,
                    CallLog.Outcome.BOOKED, CallLog.Outcome.NOT_INTERESTED]
        cands = list(RetestCandidate.objects.open().select_related("centre", "patient", "test", "source_test"))
        random.shuffle(cands)
        for c in cands[: len(cands) // 3]:
            user = User.objects.active_employees().filter(home_centre=c.centre).first()
            if user:
                call = log_call(c, user, random.choice(outcomes), booked_date=timezone.localdate() + dt.timedelta(days=random.randint(1, 5)))
                CallLog.objects.filter(pk=call.pk).update(called_at=timezone.now() - dt.timedelta(days=random.randint(0, 40)))
