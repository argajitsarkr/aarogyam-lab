"""Seed ~50 common pathology tests.

!! CLINICAL REVIEW REQUIRED !!
Prices are placeholders and re-test intervals are generic monitoring defaults.
Every seeded test is flagged `needs_clinical_review=True` until the lab's
pathologist confirms the interval and an Admin edits the price.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.patients.models import TestCatalog

H, B, HO, S, IM, MI, CP, V, CA, P = (
    "HAEMATOLOGY", "BIOCHEMISTRY", "HORMONES", "SEROLOGY", "IMMUNOLOGY",
    "MICROBIOLOGY", "CLINICAL_PATHOLOGY", "VITAMINS", "CARDIAC", "PROFILE",
)

# code, name, category, sample, price, retest_days (None = no reminder), chronic
TESTS = [
    ("CBC", "Complete Blood Count (CBC)", H, "EDTA whole blood", 300, 180, False),
    ("HB", "Haemoglobin (Hb)", H, "EDTA whole blood", 100, 90, False),
    ("ESR", "Erythrocyte Sedimentation Rate (ESR)", H, "EDTA whole blood", 100, None, False),
    ("PLT", "Platelet Count", H, "EDTA whole blood", 150, None, False),
    ("PBS", "Peripheral Blood Smear", H, "EDTA whole blood", 200, None, False),
    ("BGRH", "Blood Group & Rh Typing", H, "EDTA whole blood", 100, None, False),
    ("PTINR", "Prothrombin Time / INR", H, "Citrate plasma", 350, 30, True),
    ("RETIC", "Reticulocyte Count", H, "EDTA whole blood", 200, None, False),
    ("FBS", "Glucose — Fasting (FBS)", B, "Fluoride plasma", 60, 90, True),
    ("PPBS", "Glucose — Post Prandial (PPBS)", B, "Fluoride plasma", 60, 90, True),
    ("RBS", "Glucose — Random (RBS)", B, "Fluoride plasma", 60, None, False),
    ("HBA1C", "HbA1c (Glycated Haemoglobin)", B, "EDTA whole blood", 450, 90, True),
    ("LIPID", "Lipid Profile", B, "Serum (fasting)", 500, 180, True),
    ("KFT", "Kidney Function Test (KFT)", B, "Serum", 550, 180, True),
    ("LFT", "Liver Function Test (LFT)", B, "Serum", 550, 180, True),
    ("UREA", "Blood Urea", B, "Serum", 120, 180, False),
    ("CREAT", "Serum Creatinine", B, "Serum", 150, 180, True),
    ("URIC", "Uric Acid", B, "Serum", 150, 90, True),
    ("ELEC", "Electrolytes (Na, K, Cl)", B, "Serum", 400, 90, False),
    ("CALC", "Calcium (Total)", B, "Serum", 150, 180, False),
    ("PHOS", "Phosphorus", B, "Serum", 150, None, False),
    ("BILI", "Bilirubin (Total & Direct)", B, "Serum", 150, None, False),
    ("SGPT", "SGPT / ALT", B, "Serum", 150, 90, False),
    ("SGOT", "SGOT / AST", B, "Serum", 150, None, False),
    ("ALP", "Alkaline Phosphatase", B, "Serum", 150, None, False),
    ("PROT", "Total Protein & Albumin", B, "Serum", 200, None, False),
    ("AMYL", "Amylase", B, "Serum", 400, None, False),
    ("IRON", "Iron Studies (Iron, TIBC, Ferritin)", B, "Serum", 900, 90, False),
    ("FERR", "Ferritin", B, "Serum", 500, 90, False),
    ("TSH", "Thyroid Stimulating Hormone (TSH)", HO, "Serum", 300, 180, True),
    ("T3T4", "Thyroid Profile (T3, T4, TSH)", HO, "Serum", 500, 180, True),
    ("FT3FT4", "Free T3 / Free T4", HO, "Serum", 600, 180, True),
    ("PRL", "Prolactin", HO, "Serum", 500, None, False),
    ("PSA", "PSA (Prostate Specific Antigen)", HO, "Serum", 700, 365, True),
    ("BHCG", "Beta hCG", HO, "Serum", 700, None, False),
    ("INS", "Fasting Insulin", HO, "Serum", 700, None, False),
    ("VITD", "Vitamin D (25-OH)", V, "Serum", 1200, 90, False),
    ("VITB12", "Vitamin B12", V, "Serum", 900, 90, False),
    ("CRP", "C-Reactive Protein (CRP)", IM, "Serum", 400, None, False),
    ("RAF", "Rheumatoid Factor (RA)", IM, "Serum", 400, None, False),
    ("ASO", "ASO Titre", IM, "Serum", 400, None, False),
    ("WIDAL", "Widal Test", S, "Serum", 150, None, False),
    ("DENG", "Dengue NS1 / IgG / IgM", S, "Serum", 900, None, False),
    ("MP", "Malaria Parasite (Antigen)", S, "Whole blood", 300, None, False),
    ("HBSAG", "HBsAg", S, "Serum", 300, None, False),
    ("HCV", "Anti-HCV", S, "Serum", 500, None, False),
    ("HIV", "HIV I & II", S, "Serum", 400, None, False),
    ("VDRL", "VDRL", S, "Serum", 150, None, False),
    ("URINE", "Urine Routine & Microscopy", CP, "Urine", 120, None, False),
    ("UACR", "Urine Microalbumin / Creatinine Ratio", CP, "Urine", 600, 180, True),
    ("STOOL", "Stool Routine", CP, "Stool", 150, None, False),
    ("UCS", "Urine Culture & Sensitivity", MI, "Urine (sterile)", 700, None, False),
    ("TROP", "Troponin I", CA, "Serum", 1000, None, False),
    ("FULLBODY", "Full Body Check-up (package)", P, "Serum, EDTA, urine", 1999, 365, False),
]


class Command(BaseCommand):
    help = "Seed ~50 common tests (placeholder prices; intervals flagged for clinical review). Idempotent."

    def handle(self, *args, **options):
        created = 0
        for code, name, cat, sample, price, days, chronic in TESTS:
            _, was_created = TestCatalog.objects.get_or_create(
                code=code,
                defaults=dict(name=name, category=cat, sample_type=sample, price=Decimal(price),
                              retest_interval_days=days, is_chronic_monitoring=chronic, needs_clinical_review=True),
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"Test catalog: {created} created, {len(TESTS) - created} already present."))
        self.stdout.write(self.style.WARNING("Seeded prices are placeholders and intervals need review by the pathologist."))
