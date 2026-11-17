from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import Signal

from apps.audit.models import AuditLog
from apps.audit.services import log_event
from apps.core.validators import normalize_phone

from .models import Patient, TestCatalog, Visit, VisitTest

# Sent after a visit and all of its tests are saved. Receivers in the
# follow-up and re-test apps auto-close/convert their items.
visit_registered = Signal()


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
def patient_centre_ids(patient):
    ids = set(patient.visits.filter(deleted_at__isnull=True).values_list("centre_id", flat=True))
    ids.add(patient.registered_at_centre_id)
    return ids


def check_patient_access(user, patient, request=None):
    """Full-record access: Admins always; employees if the patient is linked to
    their home centre or a centre they were granted. Cross-centre views and
    denials are written to the audit log."""
    if user.is_admin:
        return
    linked = patient_centre_ids(patient)
    if user.home_centre_id in linked:
        return
    if linked & user.accessible_centre_ids():
        log_event(AuditLog.Action.VIEW_CROSS_CENTRE, obj=patient, user=user, request=request,
                  centre_id=user.home_centre_id, note="Opened full record via granted centre access")
        return
    log_event(AuditLog.Action.ACCESS_DENIED, obj=patient, user=user, request=request,
              centre_id=user.home_centre_id, note="Attempted to open another centre's patient record")
    raise PermissionDenied("This patient belongs to another centre. Ask an Admin for access if you need the full record.")


def check_visit_edit(user, visit):
    """Results/billing of a visit can be edited at the visit's own centre only."""
    if user.is_admin or user.home_centre_id == visit.centre_id:
        return
    raise PermissionDenied("Only staff of the centre where this visit happened can edit it.")


# --------------------------------------------------------------------------
# Lookup (cross-centre duplicate check)
# --------------------------------------------------------------------------
def lookup_patients(term):
    """Exact phone (either number) or exact patient ID match across ALL centres."""
    term = (term or "").strip()
    if not term:
        return Patient.objects.none()
    qs = Patient.objects.active().select_related("registered_at_centre")
    phone = normalize_phone(term)
    if phone and len(phone) == 10 and phone.isdigit():
        from django.db.models import Q

        return qs.filter(Q(phone=phone) | Q(alt_phone=phone))[:10]
    return qs.filter(patient_id__iexact=term)[:1]


def minimal_card(patient, user):
    last = patient.last_visit
    return {
        "patient": patient,
        "name": patient.full_name,
        "patient_id": patient.patient_id,
        "last_visit_date": last.visit_date if last else None,
        "last_visit_centre": last.centre if last else patient.registered_at_centre,
        "can_open": user.is_admin or bool(patient_centre_ids(patient) & user.accessible_centre_ids()),
    }


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
@transaction.atomic
def create_visit(*, patient, user, centre, tests, visit_fields):
    """Create a visit at `centre` with tests priced from the catalogue."""
    visit = Visit(patient=patient, centre=centre, registered_by=user, **visit_fields)
    visit.save()
    total = Decimal(0)
    for test in tests:
        VisitTest.objects.create(visit=visit, test=test, price_charged=test.price)
        total += test.price
    visit.total_amount = total
    visit.save(update_fields=["total_amount", "updated_at"])
    visit_registered.send(sender=Visit, visit=visit)
    return visit


def employee_centre(user, requested_centre=None):
    """Employees always register at their home centre; Admins choose (or use scope)."""
    if not user.is_admin:
        if not user.home_centre:
            raise PermissionDenied("Your account has no home centre. Ask an Admin.")
        return user.home_centre
    return requested_centre


def active_tests():
    return TestCatalog.objects.filter(is_active=True).order_by("name")


# --------------------------------------------------------------------------
# DPDP data-subject requests
# --------------------------------------------------------------------------
def export_patient_data(patient, user):
    from apps.audit.services import serialize_value

    def row(obj, exclude=()):
        return {f.name: serialize_value(getattr(obj, f.attname)) for f in obj._meta.concrete_fields if f.name not in exclude}

    data = {"patient": row(patient), "visits": []}
    for v in patient.visits.prefetch_related("tests__test"):
        vd = row(v)
        vd["tests"] = [dict(row(t), test_name=t.test.name) for t in v.tests.all()]
        data["visits"].append(vd)
    data["followups"] = [row(f) for f in patient.followups.all()]
    data["call_logs"] = [row(c) for cand in patient.retest_candidates.all() for c in cand.calls.all()]
    log_event(AuditLog.Action.DATA_REQUEST, obj=patient, user=user, note="DPDP data export")
    return data


@transaction.atomic
def erase_patient(patient, user):
    """Anonymise personal data while keeping de-identified clinical/billing rows
    for statutory record keeping. Irreversible."""
    from django.utils import timezone

    patient.full_name = "Erased patient"
    patient.phone = ""
    patient.alt_phone = ""
    patient.email = ""
    patient.house_street = ""
    patient.village_ward = ""
    patient.dob = None
    patient.notes = ""
    patient.consent_to_contact = False
    patient.do_not_call = True
    patient.erased_at = timezone.now()
    patient.is_active = False
    patient.save()
    for v in patient.visits.all():
        v.collection_address = ""
        v.save(update_fields=["collection_address"])
    patient.retest_candidates.filter(status__in=["PENDING", "CONTACTED", "SCHEDULED"]).update(status="CLOSED")
    patient.followups.filter(status__in=["PENDING", "CONTACTED", "SCHEDULED"]).update(status="NOT_INTERESTED")
    log_event(AuditLog.Action.DATA_REQUEST, obj=patient, user=user, note="DPDP erasure: personal data anonymised")
