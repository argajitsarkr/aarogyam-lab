"""View-preference persistence, scope switcher, saved filters, and page smoke tests."""
import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import SavedFilter
from apps.factories import PatientFactory, TestCatalogFactory, VisitFactory, reported_test
from apps.followups.models import FollowUp
from apps.retest.services import generate_candidates

pytestmark = pytest.mark.django_db


def test_view_choice_persists_across_sessions(client, employee):
    user = employee("ARP")
    client.force_login(user)
    resp = client.get(reverse("patients:list"), {"view": "card"})
    assert resp.context["view_mode"] == "card"
    client.logout()

    # New session: no ?view= param, preference is remembered from the profile
    client.force_login(User.objects.get(pk=user.pk))
    assert client.get(reverse("patients:list")).context["view_mode"] == "card"
    assert User.objects.get(pk=user.pk).ui_preferences["view:patients"] == "card"


def test_kanban_and_calendar_persist_per_page(client, employee):
    user = employee("ARP")
    client.force_login(user)
    client.get(reverse("followups:list"), {"view": "kanban"})
    client.get(reverse("retest:list"), {"view": "calendar"})
    client.get(reverse("patients:list"), {"view": "table"})
    assert client.get(reverse("followups:list")).context["view_mode"] == "kanban"
    assert client.get(reverse("retest:list")).context["view_mode"] == "calendar"
    assert client.get(reverse("patients:list")).context["view_mode"] == "table"


def test_invalid_view_mode_ignored(client, employee):
    client.force_login(employee("ARP"))
    assert client.get(reverse("patients:list"), {"view": "kanban"}).context["view_mode"] == "table"


def test_page_size_and_hidden_columns_persist(client, employee):
    user = employee("ARP")
    client.force_login(user)
    client.get(reverse("patients:list"), {"page_size": 50})
    client.post(reverse("core:save_pref"), {"key": "cols:patients", "value": '["pin","phone"]'})
    resp = client.get(reverse("patients:list"))
    assert resp.context["paginator"].per_page == 50
    assert resp.context["hidden_cols"] == ["pin", "phone"]
    assert client.post(reverse("core:save_pref"), {"key": "role", "value": "ADMIN"}).status_code == 400


def test_scope_switcher_admin_only(client, admin_user, employee, centres):
    client.force_login(admin_user)
    client.post(reverse("core:set_scope"), {"scope": f"centre:{centres['BHY'].pk}"})
    resp = client.get(reverse("patients:list"))
    assert resp.context["scope"].centre_ids == [centres["BHY"].pk]
    admin_user.refresh_from_db()
    assert admin_user.ui_preferences["scope"] == f"centre:{centres['BHY'].pk}"

    emp = employee("ARP")
    client.force_login(emp)
    client.post(reverse("core:set_scope"), {"scope": "all"})
    assert client.get(reverse("patients:list")).context["scope"].centre_ids == [centres["ARP"].pk]


def test_saved_filter_pinned(client, employee):
    user = employee("ARP")
    client.force_login(user)
    client.post(reverse("core:saved_filter_create"),
                {"page": "patients:list", "name": "Abnormal HbA1c 6m", "querystring": "flag=ABNORMAL&visit_from=2026-05-01"})
    sf = SavedFilter.objects.get(user=user)
    assert sf.get_absolute_url() == "/patients/?flag=ABNORMAL&visit_from=2026-05-01"
    assert "Abnormal HbA1c 6m" in client.get(reverse("dashboard:home")).content.decode()


# ---------------------------------------------------------------- smoke tests
@pytest.fixture
def populated(centres, admin_user, employee):
    emp = employee("ARP")
    hba1c = TestCatalogFactory(code="HBA1C", retest_interval_days=90, is_chronic_monitoring=True)
    p = PatientFactory(registered_at_centre=centres["ARP"], locality="Ram Nagar", pin_code="799002")
    vt = reported_test(p, hba1c, days_ago=95, flag="ABNORMAL")
    vt.save()
    FollowUp.objects.create(patient=p, centre=centres["ARP"], due_date=timezone.localdate())
    generate_candidates()
    return {"emp": emp, "admin": admin_user, "patient": p, "visit": vt.visit, "test": hba1c}


def _pages(d):
    p, v = d["patient"], d["visit"]
    fu = FollowUp.objects.first()
    pages = [
        reverse("dashboard:home"), reverse("patients:list"), reverse("patients:list") + "?view=card",
        reverse("patients:register"), reverse("patients:register_new"), reverse("patients:lookup") + f"?term={p.phone}",
        reverse("patients:detail", args=[p.pk]), reverse("patients:update", args=[p.pk]),
        reverse("patients:visit_detail", args=[v.pk]), reverse("patients:new_visit", args=[p.pk]),
        reverse("patients:doctors"), reverse("patients:doctor_create"), reverse("patients:tests"),
        reverse("patients:localities") + "?q=Ram",
        reverse("followups:list"), reverse("followups:create") + f"?patient={p.pk}", reverse("followups:detail", args=[fu.pk]),
        reverse("retest:my_calls"), reverse("retest:list"),
        reverse("pricing:compare"), reverse("pricing:lookup") + f"?test={d['test'].pk}",
        reverse("pricing:package") + f"?tests={d['test'].pk}",
        reverse("accounts:password_change"),
    ]
    for mode in ("table", "card", "kanban", "calendar"):
        pages.append(reverse("followups:list") + f"?view={mode}")
        pages.append(reverse("retest:list") + f"?view={mode}")
    for cal in ("month", "week", "day"):
        pages.append(reverse("followups:list") + f"?view=calendar&cal={cal}")
    return pages


ADMIN_ONLY = ["dashboard:compare", "dashboard:map", "retest:analytics", "patients:import", "pricing:manage",
              "pricing:bulk_upload", "accounts:user_list", "centres:list", "centres:create",
              "audit:list", "core:settings", "patients:test_create", "pricing:competitor_create"]


def test_every_page_renders_for_employee(client, populated):
    client.force_login(populated["emp"])
    for url in _pages(populated):
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
    for name in ADMIN_ONLY:
        assert client.get(reverse(name)).status_code == 403, name


def test_every_page_renders_for_admin(client, populated):
    client.force_login(populated["admin"])
    for url in _pages(populated) + [reverse(n) for n in ADMIN_ONLY]:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"


def test_htmx_partial_results(client, populated):
    client.force_login(populated["emp"])
    resp = client.get(reverse("patients:list"), {"q": populated["patient"].full_name[:4]},
                      HTTP_HX_REQUEST="true", HTTP_HX_TARGET="list-results")
    assert resp.status_code == 200
    assert "<html" not in resp.content.decode()


def test_noindex_and_login_only(client):
    resp = client.get(reverse("accounts:login"))
    assert resp.status_code == 200 and resp["X-Robots-Tag"].startswith("noindex")
    assert 'name="robots" content="noindex' in resp.content.decode()
    assert client.get(reverse("dashboard:home")).status_code == 302


def test_healthz_bypasses_host_check_and_https_redirect(client, settings):
    settings.ALLOWED_HOSTS = ["lab.example.in"]
    settings.SECURE_SSL_REDIRECT = True
    resp = client.get("/healthz", HTTP_HOST="localhost:8000")
    assert resp.status_code == 200 and resp.content == b"ok"


def test_kombu_redis_transport_importable():
    # The server's celery containers crashed on `import packaging` from kombu's redis transport.
    import kombu.transport.redis  # noqa: F401
