"""Static files are served under content-hashed names in production.

Without this a deploy reuses /static/dist/app.css, and both the browser (a year
of Cache-Control) and Cloudflare's edge keep serving the previous build - the
"why hasn't the site changed yet" problem.
"""
import pytest
from django.core.exceptions import SuspiciousFileOperation

from apps.core.storage import ForgivingManifestStaticFilesStorage


def test_production_uses_hashed_static_names(monkeypatch):
    """The backend is only swapped in when DEBUG is off, so local runs keep plain
    filenames and need no collectstatic before every page load."""
    import importlib
    import os

    import config.settings as conf

    monkeypatch.setitem(os.environ, "DEBUG", "False")
    monkeypatch.setitem(os.environ, "SECRET_KEY", "x" * 60)
    try:
        reloaded = importlib.reload(conf)
        assert reloaded.STORAGES["staticfiles"]["BACKEND"] == (
            "apps.core.storage.ForgivingManifestStaticFilesStorage"
        )
        assert not hasattr(importlib.reload(conf), "_never")  # keep the reload explicit
    finally:
        monkeypatch.undo()
        importlib.reload(conf)  # leave the suite with the DEBUG settings it started with


@pytest.mark.parametrize("error", [ValueError("missing"), SuspiciousFileOperation("outside root")])
def test_a_dead_reference_does_not_fail_the_deploy(monkeypatch, error):
    """A url() pointing at a file we do not ship must leave the url alone rather
    than abort collectstatic, which would abort the whole deploy."""
    storage = ForgivingManifestStaticFilesStorage()

    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage.hashed_name", boom
    )
    assert storage.hashed_name("vendor/leaflet/images/gone.png") == "vendor/leaflet/images/gone.png"


def test_entrypoint_skips_the_tailwind_source():
    """static/src/app.css is build input: its @import lines point at node_modules and
    at templates/, which the hashing storage cannot resolve."""
    from pathlib import Path

    entrypoint = (Path(__file__).resolve().parents[3] / "docker" / "entrypoint.sh").read_text()
    line = next(ln for ln in entrypoint.splitlines() if "collectstatic" in ln)
    assert "--ignore=src" in line
