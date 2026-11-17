"""factory_boy factories shared by the test suite."""
import datetime as dt
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.models import User
from apps.centres.models import Centre
from apps.patients.models import Doctor, Patient, TestCatalog, Visit, VisitTest


class CentreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Centre
        django_get_or_create = ("short_code",)

    name = factory.Sequence(lambda n: f"Centre {n}")
    short_code = factory.Sequence(lambda n: "C" + "ABCDEFGHIJ"[n % 10] + "ABCDEFGHIJ"[(n // 10) % 10])


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name")
    role = User.Role.EMPLOYEE
    home_centre = factory.SubFactory(CentreFactory)
    must_change_password = False
    password = factory.PostGenerationMethodCall("set_password", "s3cure-Passw0rd!")

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class AdminFactory(UserFactory):
    role = User.Role.ADMIN
    home_centre = None
    is_staff = True


class TestCatalogFactory(factory.django.DjangoModelFactory):
    __test__ = False  # not a pytest test class

    class Meta:
        model = TestCatalog
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"T{n:03d}")
    name = factory.Sequence(lambda n: f"Test {n}")
    price = Decimal("300")
    retest_interval_days = 90


class DoctorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doctor

    name = factory.Faker("name")


class PatientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Patient

    full_name = factory.Faker("name")
    sex = "F"
    age_years = 45
    phone = factory.Sequence(lambda n: f"9{n:09d}")
    registered_at_centre = factory.SubFactory(CentreFactory)
    consent_to_contact = True


class VisitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Visit

    patient = factory.SubFactory(PatientFactory)
    centre = factory.LazyAttribute(lambda o: o.patient.registered_at_centre)
    visit_date = factory.LazyFunction(timezone.localdate)


class VisitTestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VisitTest

    visit = factory.SubFactory(VisitFactory)
    test = factory.SubFactory(TestCatalogFactory)
    price_charged = Decimal("300")


def reported_test(patient, test, days_ago, flag="", centre=None):
    """Create a visit `days_ago` with one reported test."""
    date = timezone.localdate() - dt.timedelta(days=days_ago)
    visit = VisitFactory(patient=patient, centre=centre or patient.registered_at_centre, visit_date=date)
    return VisitTestFactory(visit=visit, test=test, result_status="REPORTED", report_date=date, flag=flag)
