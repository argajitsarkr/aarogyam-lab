"""Sitemaps for the public half only.

The staff app is disallowed in robots.txt and must never appear here. Every
sitemap below is restricted to rows that are actually published, so a test
switched off with `is_public` disappears from the sitemap on the next fetch
rather than becoming a 404 that a crawler keeps retrying.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.centres.models import Centre
from apps.patients.models import TestCatalog

from .models import Doctor, HealthConcern, MedicineCategory


class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return ["public:home", "public:tests", "public:medicines", "public:centres",
                "public:doctors", "public:prescription", "public:about", "public:contact"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):  # noqa: F811 - the home page outranks the rest
        return 1.0 if item == "public:home" else 0.8


class CentreSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.9

    def items(self):
        return Centre.objects.filter(is_active=True, is_public=True)

    def lastmod(self, obj):
        return obj.updated_at


class TestSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return TestCatalog.objects.filter(is_active=True, is_public=True)

    def location(self, obj):
        return reverse("public:test", args=[obj.code])

    def lastmod(self, obj):
        return obj.updated_at


class ConcernSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return HealthConcern.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class MedicineCategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return MedicineCategory.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class DoctorSitemap(Sitemap):
    """Doctors have no page of their own yet, so the listing stands in for them -
    one entry, not one per doctor, which would be a duplicate-content problem."""

    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["public:doctors"] if Doctor.objects.published().exists() else []

    def location(self, item):
        return reverse(item)


SITEMAPS = {
    "pages": StaticViewSitemap,
    "centres": CentreSitemap,
    "tests": TestSitemap,
    "concerns": ConcernSitemap,
    "medicines": MedicineCategorySitemap,
    "doctors": DoctorSitemap,
}
