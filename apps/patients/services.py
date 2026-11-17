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
        VisitTest.objects.create(visit=visit, test=test)
        total += test.price
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
