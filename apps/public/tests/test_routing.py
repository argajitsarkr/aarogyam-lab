"""The Phase 0 routing split: the staff app moved under /staff/, the public
site took the root. These assert the two halves are told apart by path."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_public_home_is_open_and_indexable(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "X-Robots-Tag" not in resp


@pytest.mark.django_db
def test_staff_dashboard_lives_under_staff_and_needs_a_session(client):
    assert reverse("dashboard:home") == "/staff/"
    resp = client.get("/staff/")
    assert resp.status_code == 302
    assert resp["Location"] == "/accounts/login/?next=/staff/"


@pytest.mark.django_db
def test_staff_pages_are_never_indexed(client, admin_user):
    client.force_login(admin_user)
    resp = client.get("/staff/")
    assert resp["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    assert resp["Cache-Control"] == "private, no-store"


@pytest.mark.django_db
def test_login_page_is_open_but_not_indexed(client):
    resp = client.get("/accounts/login/")
    assert resp.status_code == 200
    assert resp["X-Robots-Tag"] == "noindex, nofollow, noarchive"


def test_robots_disallows_only_the_staff_half(client):
    body = client.get("/robots.txt").content.decode()
    assert "Disallow: /staff/" in body
    assert "Disallow: /\n" not in body
