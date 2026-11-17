"""Login behaviour aligned with the TGMA platform (see CLAUDE.md, Accounts)."""
import pytest
from django.conf import settings
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.factories import UserFactory

pytestmark = pytest.mark.django_db
PW = "s3cure-Passw0rd!"  # factory default
LOGIN = reverse("accounts:login")


@pytest.fixture(autouse=True)
def _axes_on(settings):
    # conftest.py turns django-axes off suite-wide; the lockout is what is under test here.
    settings.AXES_ENABLED = True


def _post(client, username, password):
    return client.post(LOGIN, {"username": username, "password": password})


def _notes(action):
    return list(AuditLog.objects.filter(action=action).values_list("note", flat=True))


def test_same_message_for_unknown_user_and_bad_password(client, centres):
    UserFactory(username="asha", home_centre=centres["ARP"])
    a = _post(client, "nobody", "whatever-123456").content
    b = _post(client, "asha", "wrong-password-1").content
    assert b"Please enter a correct" in a and b"Please enter a correct" in b
    notes = _notes("LOGIN_FAILED")
    assert any("unknown user" in n for n in notes) and any("bad password" in n for n in notes)


def test_inactive_account_reason_logged_but_not_shown(client, centres):
    UserFactory(username="gone", home_centre=centres["ARP"], is_active=False)
    resp = _post(client, "gone", PW)
    assert b"Please enter a correct" in resp.content
    assert any("inactive account" in n for n in _notes("LOGIN_FAILED"))


def test_lockout_after_five_failures_then_blocked_even_with_right_password(client, centres):
    UserFactory(username="typo", home_centre=centres["ARP"])
    for _ in range(settings.AXES_FAILURE_LIMIT):
        _post(client, "typo", "wrong-password-1")
    resp = _post(client, "typo", PW)  # correct password, but locked
    assert resp.status_code == 429
    assert b"Try again in 15 minutes" in resp.content
    assert any("account locked" in n for n in _notes("LOGIN_BLOCKED"))
    assert not AuditLog.objects.filter(action="LOGIN").exists()


def test_lock_is_fifteen_minutes():
    assert settings.AXES_COOLOFF_TIME == 0.25


def test_welcome_message_and_login_audit(client, centres):
    UserFactory(username="asha", first_name="Asha", last_name="Das", home_centre=centres["ARP"])
    resp = _post(client, "asha", PW)
    assert resp.status_code == 302
    msgs = [str(m) for m in resp.wsgi_request._messages]
    assert "Welcome, Asha Das." in msgs
    assert AuditLog.objects.filter(action="LOGIN", object_repr__icontains="asha").exists()


def test_forced_change_must_differ_and_is_audited(client, centres):
    user = UserFactory(username="newbie", home_centre=centres["ARP"], must_change_password=True)
    client.force_login(user)
    url = reverse("accounts:password_change")
    same = client.post(url, {"old_password": PW, "new_password1": PW, "new_password2": PW})
    assert b"must be different" in same.content
    new = "another-Long-pass-77"
    ok = client.post(url, {"old_password": PW, "new_password1": new, "new_password2": new})
    assert ok.status_code == 302
    user.refresh_from_db()
    assert not user.must_change_password and user.check_password(new)
    assert any("first-login" in n for n in _notes("PASSWORD_CHANGED"))


def test_logout_is_post_only_and_confirms(client, centres):
    client.force_login(UserFactory(home_centre=centres["ARP"]))
    assert client.get(reverse("accounts:logout")).status_code == 405
    resp = client.post(reverse("accounts:logout"), follow=True)
    assert b"You have been logged out." in resp.content
    assert AuditLog.objects.filter(action="LOGOUT").exists()


def test_own_cookie_names():
    assert settings.SESSION_COOKIE_NAME == "aarogyam_session"
    assert settings.CSRF_COOKIE_NAME == "aarogyam_csrftoken"
