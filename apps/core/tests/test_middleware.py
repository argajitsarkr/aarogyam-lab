"""Headers the two halves of the site must carry.

The staff half is never indexed and never stored; the public half is indexable
and revalidated. `is_staff_area()` is the single rule behind both.
"""
import pytest


@pytest.mark.django_db
def test_a_public_page_says_revalidate_rather_than_nothing(client):
    """No Cache-Control at all is not the same as "do not cache": a browser is
    free to reuse the page heuristically, and a redeploy then looks like it did
    not land. That is what happened after the staff/public split."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp["Cache-Control"] == "public, max-age=0, must-revalidate"
    assert "X-Robots-Tag" not in resp
