"""Builds the price matrix with two queries total (fast for 500 tests x 6 labs).

Aarogyam does not compete on these prices: the customer picks a company and the
lab earns a commission, so the matrix lists each company's price and nothing else -
no "our price" column, no cheapest-wins highlight, no savings.
"""
from django.utils import timezone

from apps.core.models import SiteSettings
from apps.patients.models import TestCatalog

from .models import Competitor, CompetitorPrice


def build_matrix(test_ids=None, q=None, category=None):
    stale_days = SiteSettings.load().price_stale_days
    today = timezone.localdate()
    competitors = list(Competitor.objects.filter(is_active=True))
    tests = TestCatalog.objects.filter(is_active=True).only("id", "code", "name", "category", "price")
    if test_ids is not None:
        tests = tests.filter(pk__in=test_ids)
    if q:
        from django.db.models import Q

        tests = tests.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if category:
        tests = tests.filter(category=category)
    tests = list(tests.order_by("name"))
    prices = {}
    for p in (CompetitorPrice.objects.filter(test_id__in=[t.pk for t in tests], competitor__is_active=True)
              .values("test_id", "competitor_id", "price", "last_verified_on", "source_note")):
        p["stale"] = (today - p["last_verified_on"]).days > stale_days
        prices[(p["test_id"], p["competitor_id"])] = p
    rows = []
    for t in tests:
        cells = [prices.get((t.pk, c.pk)) for c in competitors]
        quoted = [c["price"] for c in cells if c]
        rows.append({
            "test": t, "cells": cells, "pairs": list(zip(competitors, cells)),
            "lowest": min(quoted) if quoted else None,
            "highest": max(quoted) if quoted else None,
            "quoted_count": len(quoted),
        })
    return competitors, rows


def package_totals(competitors, rows):
    """Total per lab for the selected tests; a lab missing any test is flagged incomplete."""
    out = []
    for i, c in enumerate(competitors):
        vals = [r["cells"][i]["price"] for r in rows if r["cells"][i]]
        out.append({"competitor": c, "total": sum(vals) if vals else None, "missing": len(rows) - len(vals),
                    "complete": bool(vals) and len(vals) == len(rows)})
    return out
