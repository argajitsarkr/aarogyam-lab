"""Server-side account management (TGMA model): seed_users, unlock_user, reset_password."""
from io import StringIO

import pytest
from axes.models import AccessAttempt
from django.core.management import call_command
from django.urls import reverse

import apps.accounts.management.commands.seed_users as seed_cmd
from apps.accounts import seed_users as seed_module
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.factories import AdminFactory, UserFactory

pytestmark = pytest.mark.django_db

PW = "Seed-Password-2026!"


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.fixture
def seed_list(monkeypatch, centres):
    users = [
        {"username": "dev@example.com", "first_name": "Dev", "last_name": "One", "role": "ADMIN",
         "home_centre": None, "extra_centres": [], "password_env": "SEED_PW_DEV"},
        {"username": "desk@example.com", "first_name": "Desk", "last_name": "Two", "role": "EMPLOYEE",
         "home_centre": "RRM", "extra_centres": ["BHY"], "password_env": "SEED_PW_DESK"},
    ]
    monkeypatch.setattr(seed_cmd, "SEED_USERS", users)
    monkeypatch.setattr(seed_cmd, "REMOVE_USERS", [])
    return users


class TestSeedUsers:
    def test_shipped_list_is_only_the_developer(self):
        assert [u["username"] for u in seed_module.SEED_USERS] == ["argajit05@gmail.com"]
        assert seed_module.SEED_USERS[0]["role"] == "ADMIN"

    def test_creates_users_from_env_with_forced_change(self, seed_list, monkeypatch, centres):
        monkeypatch.setenv("SEED_PW_DEV", PW)
        monkeypatch.setenv("SEED_PW_DESK", PW)
        out = run("seed_users")
        assert "2 created" in out
        dev = User.objects.get(username="dev@example.com")
        assert dev.is_admin and dev.is_superuser and dev.must_change_password and dev.check_password(PW)
        assert dev.email == "dev@example.com"
        desk = User.objects.get(username="desk@example.com")
        assert desk.home_centre == centres["RRM"] and list(desk.extra_centres.all()) == [centres["BHY"]]

    def test_skips_new_user_without_env_password(self, seed_list, monkeypatch):
        monkeypatch.setenv("SEED_PW_DEV", PW)
        monkeypatch.delenv("SEED_PW_DESK", raising=False)
        out = run("seed_users")
        assert "set SEED_PW_DESK" in out
        assert not User.objects.filter(username="desk@example.com").exists()

    def test_rejects_weak_env_password(self, seed_list, monkeypatch):
        monkeypatch.setenv("SEED_PW_DEV", "short")
        out = run("seed_users")
        assert "rejected" in out and not User.objects.filter(username="dev@example.com").exists()

    def test_rerun_keeps_changed_password(self, seed_list, monkeypatch):
        monkeypatch.setenv("SEED_PW_DEV", PW)
        run("seed_users")
        dev = User.objects.get(username="dev@example.com")
        dev.set_password("Their-Own-Password-1")
        dev.must_change_password = False
        dev.save()
        run("seed_users")
        dev.refresh_from_db()
        assert dev.check_password("Their-Own-Password-1") and not dev.must_change_password

    def test_reset_passwords_flag(self, seed_list, monkeypatch):
        monkeypatch.setenv("SEED_PW_DEV", PW)
        run("seed_users")
        dev = User.objects.get(username="dev@example.com")
        dev.set_password("Their-Own-Password-1")
        dev.must_change_password = False
        dev.save()
        run("seed_users", "--reset-passwords")
        dev.refresh_from_db()
        assert dev.check_password(PW) and dev.must_change_password

    def test_never_reenables_deactivated_user(self, seed_list, monkeypatch):
        monkeypatch.setenv("SEED_PW_DEV", PW)
        run("seed_users")
        User.objects.filter(username="dev@example.com").update(is_active=False)
        run("seed_users")
        assert not User.objects.get(username="dev@example.com").is_active


def _lock(username):
    AccessAttempt.objects.create(username=username, ip_address="10.0.0.1", user_agent="t",
                                 failures_since_start=5, get_data="", post_data="", http_accept="", path_info="/")


class TestUnlockAndReset:
    def test_unlock_user(self, centres):
        UserFactory(username="ravi", home_centre=centres["ARP"])
        _lock("ravi")
        out = run("unlock_user", "ravi")
        assert "ravi" in out and not AccessAttempt.objects.filter(username="ravi").exists()

    def test_reset_password_prints_temp_and_forces_change(self, centres):
        user = UserFactory(username="ravi", home_centre=centres["ARP"])
        _lock("ravi")
        out = run("reset_password", "ravi")
        user.refresh_from_db()
        assert user.must_change_password
        assert any(user.check_password(tok) for tok in out.split())
        assert not AccessAttempt.objects.filter(username="ravi").exists()
        assert AuditLog.objects.filter(action="UPDATE", object_id=str(user.pk), note__icontains="password").exists()


class TestUserListReadOnly:
    def test_no_management_controls_and_shows_lock(self, client, centres):
        admin = AdminFactory(username="boss")
        UserFactory(username="ravi", home_centre=centres["ARP"])
        _lock("ravi")
        client.force_login(admin)
        html = client.get(reverse("accounts:user_list")).content.decode()
        assert "deploy.sh seed-users" in html and "locked" in html
        for word in ("Add user", ">Edit<", ">Unlock<", ">Remove<"):
            assert word not in html
