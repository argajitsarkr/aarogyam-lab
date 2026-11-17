"""Bulk import of historical patients from Excel/CSV.

Flow: upload -> map columns -> validate & preview -> commit.
Optional columns (visit_date, test_codes, result_flag) create a historical,
already-reported visit so the re-test engine can work with legacy data.
"""
import datetime as dt
import re
import uuid
from pathlib import Path

import tablib
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.centres.models import TRIPURA_DISTRICTS, Centre
from apps.core.validators import PHONE_RE, PIN_RE, normalize_phone

from .models import Patient, TestCatalog, Visit, VisitTest

TARGET_FIELDS = [
    ("full_name", "Full name", True),
    ("phone", "Phone", True),
    ("sex", "Sex (M/F/O)", True),
    ("age_years", "Age (years)", False),
    ("dob", "Date of birth", False),
    ("alt_phone", "Alternate phone", False),
    ("email", "Email", False),
    ("house_street", "House / street", False),
    ("locality", "Locality / area", False),
    ("village_ward", "Village / ward", False),
    ("city", "City", False),
    ("district", "District", False),
    ("state", "State", False),
    ("pin_code", "PIN code", False),
    ("consent_to_contact", "Consent to contact (yes/no)", False),
    ("centre_code", "Centre code (ARP/RRM/BHY)", False),
    ("visit_date", "Last visit date", False),
    ("test_codes", "Test codes (comma separated)", False),
    ("result_flag", "Result flag (Normal/Borderline/Abnormal)", False),
    ("notes", "Notes", False),
]
SYNONYMS = {
    "full_name": ["name", "patient name", "full name", "patient"],
    "phone": ["phone", "mobile", "mobile no", "phone no", "contact", "contact no"],
    "sex": ["sex", "gender"],
    "age_years": ["age", "age (years)"],
    "dob": ["dob", "date of birth", "birth date"],
    "alt_phone": ["alternate phone", "alt phone", "phone 2", "alternate mobile"],
    "email": ["email", "e-mail"],
    "house_street": ["address", "house", "street", "house/street"],
    "locality": ["locality", "area"],
    "village_ward": ["village", "ward", "village/ward"],
    "city": ["city", "town"],
    "district": ["district"],
    "state": ["state"],
    "pin_code": ["pin", "pincode", "pin code", "postal code"],
    "consent_to_contact": ["consent", "consent to contact"],
    "centre_code": ["centre", "center", "centre code", "branch"],
    "visit_date": ["visit date", "date", "last visit", "test date", "report date"],
    "test_codes": ["tests", "test codes", "test code", "test"],
    "result_flag": ["flag", "result", "result flag"],
    "notes": ["notes", "remarks"],
}
DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y")


def import_dir():
    d = Path(settings.PRIVATE_MEDIA_ROOT) / "imports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(f):
    ext = ".xlsx" if f.name.lower().endswith(".xlsx") else ".csv"
    token = uuid.uuid4().hex
    path = import_dir() / f"{token}{ext}"
    with open(path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    return token, path.name


def load_dataset(filename):
    path = import_dir() / Path(filename).name  # never trust a path from the session
    if path.suffix == ".xlsx":
        with open(path, "rb") as fh:
            return tablib.Dataset().load(fh, format="xlsx")
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return tablib.Dataset().load(raw.decode(enc), format="csv")
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not read CSV file encoding.")


def guess_mapping(headers):
    mapping = {}
    norm = {h: re.sub(r"\s+", " ", str(h or "").strip().lower()) for h in headers}
    for field, *_ in TARGET_FIELDS:
        for h, n in norm.items():
            if n == field.replace("_", " ") or n in SYNONYMS.get(field, []):
                if h not in mapping.values():
                    mapping[field] = h
                    break
    return mapping


def _parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date '{s}' (use DD-MM-YYYY)")


def _clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def validate_rows(dataset, mapping, default_centre):
    centres = {c.short_code: c for c in Centre.objects.all()}
    tests = {t.code.upper(): t for t in TestCatalog.objects.all()}
    existing = set(Patient.objects.values_list("phone", "full_name"))
    headers = dataset.headers
    rows = []
    for idx, raw in enumerate(dataset, start=2):
        rec = dict(zip(headers, raw))
        get = lambda f: _clean(rec.get(mapping.get(f))) if mapping.get(f) else ""  # noqa: E731
        errors, data = [], {}
        data["full_name"] = get("full_name")[:150]
        if not data["full_name"]:
            errors.append("Name missing")
        data["phone"] = normalize_phone(get("phone"))
        if not PHONE_RE.match(data["phone"] or ""):
            errors.append(f"Invalid phone '{get('phone')}'")
        sex = get("sex").upper()[:1]
        data["sex"] = {"M": "M", "F": "F", "O": "O"}.get(sex, "")
        if not data["sex"]:
            errors.append("Sex must be M/F/O")
        age = get("age_years")
        try:
            data["age_years"] = int(float(age)) if age else None
        except ValueError:
            errors.append(f"Invalid age '{age}'")
        for f in ("dob", "visit_date"):
            try:
                data[f] = _parse_date(rec.get(mapping.get(f)) if mapping.get(f) else None)
            except ValueError as e:
                errors.append(str(e))
        if not data.get("age_years") and not data.get("dob"):
            errors.append("Age or DOB required")
        alt = normalize_phone(get("alt_phone"))
        data["alt_phone"] = alt if alt and PHONE_RE.match(alt) else ""
        for f in ("email", "house_street", "locality", "village_ward", "notes"):
            data[f] = get(f)
        data["city"] = get("city") or "Agartala"
        district = get("district")
        data["district"] = next((d for d in TRIPURA_DISTRICTS if d.lower() == district.lower()), "Other" if district else "West Tripura")
        data["state"] = get("state") or "Tripura"
        pin = get("pin_code")
        if pin and not PIN_RE.match(pin):
            errors.append(f"Invalid PIN '{pin}'")
        data["pin_code"] = pin if pin and PIN_RE.match(pin) else ""
        data["consent_to_contact"] = get("consent_to_contact").lower() in ("y", "yes", "true", "1")
        code = get("centre_code").upper()
        data["centre"] = centres.get(code) if code else default_centre
        if code and not data["centre"]:
            errors.append(f"Unknown centre code '{code}'")
        codes = [c.strip().upper() for c in get("test_codes").split(",") if c.strip()]
        unknown = [c for c in codes if c not in tests]
        if unknown:
            errors.append(f"Unknown test codes: {', '.join(unknown)}")
        data["tests"] = [tests[c] for c in codes if c in tests]
        if data["tests"] and not data.get("visit_date"):
            errors.append("Visit date required when tests are given")
        flag = get("result_flag").upper()
        data["flag"] = flag if flag in ("NORMAL", "BORDERLINE", "ABNORMAL") else ""
        key = (data["phone"], data["full_name"])
        duplicate = key in existing  # already in DB, or earlier in this same file
        if not errors:
            existing.add(key)
        status = "error" if errors else ("duplicate" if duplicate else "ok")
        rows.append({"line": idx, "data": data, "errors": errors, "status": status})
    return rows


@transaction.atomic
def commit_rows(rows, user):
    created = 0
    for row in rows:
        if row["status"] != "ok":
            continue
        d = dict(row["data"])
        tests, flag, visit_date, centre = d.pop("tests"), d.pop("flag"), d.pop("visit_date"), d.pop("centre")
        patient = Patient.objects.create(registered_at_centre=centre, registered_by=user, **d)
        if tests and visit_date:
            visit = Visit.objects.create(patient=patient, centre=centre, visit_date=visit_date, registered_by=user,
                                         notes="Imported historical visit")
            for t in tests:
                VisitTest.objects.create(visit=visit, test=t, result_status="REPORTED",
                                         report_date=visit_date, flag=flag)
        created += 1
    return created


def cleanup_old_imports(max_age_hours=24):
    cutoff = timezone.now().timestamp() - max_age_hours * 3600
    for p in import_dir().glob("*"):
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)
