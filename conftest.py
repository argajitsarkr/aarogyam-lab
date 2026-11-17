import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _isolate(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.SECURE_SSL_REDIRECT = False
    settings.AXES_ENABLED = False
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def centres(db):
    from apps.centres.models import Centre

    arp = Centre.objects.create(name="Aarogyam Pathology", short_code="ARP", is_head_centre=True)
    rrm = Centre.objects.create(name="Radha Rani MediClinic", short_code="RRM")
    bhy = Centre.objects.create(name="BeHealthy", short_code="BHY")
    return {"ARP": arp, "RRM": rrm, "BHY": bhy}


@pytest.fixture
def admin_user(db):
    from apps.factories import AdminFactory

    return AdminFactory(username="boss")


@pytest.fixture
def employee(centres):
    from apps.factories import UserFactory

    def make(code, **kw):
        return UserFactory(home_centre=centres[code], **kw)

    return make


@pytest.fixture
def login(client):
    def do(user):
        client.force_login(user)
        return client

    return do
