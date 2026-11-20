import datetime as dt
import time
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.factories import TestCatalogFactory
from apps.patients.models import TestCatalog
from apps.pricing.models import Competitor, CompetitorPrice
from apps.pricing.services import build_matrix

pytestmark = pytest.mark.django_db


@pytest.fixture
def competitors(db):
    from django.core.management import call_command

    call_command("seed_competitors", verbosity=0)
    return list(Competitor.objects.all())


def test_seed_competitors(competitors):
    assert {c.name for c in competitors} == {"Agilus Diagnostics", "Dr Lal PathLabs",
                                             "Metropolis Healthcare", "PathCare Labs"}


def test_employee_cannot_edit_prices(client, employee, competitors):
    t = TestCatalogFactory(price=300)
    client.force_login(employee("ARP"))
    assert client.get(reverse("pricing:manage")).status_code == 403
    resp = client.post(reverse("pricing:save_grid"), {f"price_{t.pk}_{competitors[0].pk}": "999"})
    assert resp.status_code == 403
    assert not CompetitorPrice.objects.exists()
    assert client.get(reverse("pricing:bulk_upload")).status_code == 403
    assert client.post(reverse("patients:test_update", args=[t.pk]), {"price": "1"}).status_code == 403
    t.refresh_from_db()
    assert t.price == 300
    # but they can view
    assert client.get(reverse("pricing:compare")).status_code == 200
    assert client.get(reverse("pricing:lookup"), {"test": t.pk}).status_code == 200


def test_admin_grid_save(client, admin_user, competitors):
    t = TestCatalogFactory(price=300)
    client.force_login(admin_user)
    client.post(reverse("pricing:save_grid"), {f"price_{t.pk}_{competitors[0].pk}": "450", f"orig_{t.pk}_{competitors[0].pk}": "",
                                               "source_note": "website", "verified_on": timezone.localdate().isoformat()})
    cp = CompetitorPrice.objects.get()
    assert cp.price == 450 and cp.entered_by == admin_user and cp.source_note == "website"


def test_matrix_lists_company_prices_with_staleness(competitors):
    """No 'our price' and no savings: the matrix is each company's own price."""
    t = TestCatalogFactory(price=Decimal("400"))
    old = timezone.localdate() - dt.timedelta(days=120)
    CompetitorPrice.objects.create(test=t, competitor=competitors[0], price=500)
    CompetitorPrice.objects.create(test=t, competitor=competitors[1], price=700, last_verified_on=old)
    _, rows = build_matrix()
    row = rows[0]
    assert row["lowest"] == 500 and row["highest"] == 700 and row["quoted_count"] == 2
    assert row["cells"][1]["stale"] is True and row["cells"][0]["stale"] is False
    assert "save_vs_cheapest" not in row and "cheapest" not in row


def test_package_totals(client, employee, competitors):
    a, b = TestCatalogFactory(price=100), TestCatalogFactory(price=200)
    for t, p in ((a, 150), (b, 260)):
        CompetitorPrice.objects.create(test=t, competitor=competitors[0], price=p)
    client.force_login(employee("ARP"))
    resp = client.get(reverse("pricing:package"), {"tests": [a.pk, b.pk]})
    assert "ours" not in resp.context
    first = resp.context["totals"][0]
    assert first["total"] == 410 and first["complete"] is True
    assert "saving" not in first


def test_comparison_page_fast_for_500_tests_x_6_labs(client, employee, competitors):
    Competitor.objects.create(name="Fifth Lab")
    Competitor.objects.create(name="Sixth Lab")
    comps = list(Competitor.objects.all())
    assert len(comps) == 6
    tests = TestCatalog.objects.bulk_create(
        [TestCatalog(code=f"P{i:04d}", name=f"Perf test {i}", price=100 + i) for i in range(500)])
    CompetitorPrice.objects.bulk_create(
        [CompetitorPrice(test=t, competitor=c, price=200 + i) for i, t in enumerate(tests) for c in comps])
    client.force_login(employee("ARP"))
    client.get(reverse("pricing:compare"))  # warm-up (template compile)
    start = time.perf_counter()
    resp = client.get(reverse("pricing:compare"))
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert len(resp.context["rows"]) == 500
    assert elapsed < 1.0, f"comparison page took {elapsed:.2f}s"
