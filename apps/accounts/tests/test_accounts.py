import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.forms import UserForm
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.models import SiteSettings
from apps.factories import AdminFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestAdminCap:
    def test_fourth_admin_rejected_at_model_level(self):
        AdminFactory.create_batch(3)
        with pytest.raises(ValidationError, match="at most 3 active Admins"):
            AdminFactory()

    def test_developer_account_does_not_use_an_admin_slot(self, settings):
        settings.DEVELOPER_ACCOUNTS = ["dev@example.com"]
        dev = AdminFactory(username="dev@example.com")
        AdminFactory.create_batch(3)  # the lab still gets all three of its own Admins
        assert dev.is_admin and User.objects.active_admins().count() == 3
        with pytest.raises(ValidationError, match="at most 3 active Admins"):
            AdminFactory()

    def test_fourth_admin_rejected_by_form(self):
        AdminFactory.create_batch(3)
        form = UserForm(data={"username": "fourth", "role": "ADMIN", "password": "Very-Long-Pass-123", "is_active": True})
        assert not form.is_valid()
        assert "at most 3 active Admins" in str(form.errors)

    def test_deactivated_admin_frees_a_slot(self):
        admins = AdminFactory.create_batch(3)
        admins[0].is_active = False
        admins[0].save()
        AdminFactory()  # no error
        assert User.objects.active_admins().count() == 3

    def test_existing_admin_can_still_be_edited_at_cap(self):
        admins = AdminFactory.create_batch(3)
        admins[1].first_name = "Renamed"
        admins[1].save()  # must not count itself


class TestEmployeeCap:
    def test_eleventh_employee_rejected(self, centres):
        for i in range(10):
            UserFactory(home_centre=centres["ARP"])
        form = UserForm(data={"username": "eleven", "role": "EMPLOYEE", "home_centre": centres["RRM"].pk,
                              "password": "Very-Long-Pass-123", "is_active": True})
        assert not form.is_valid()
        assert "employee limit (10)" in str(form.errors)
        with pytest.raises(ValidationError):
            UserFactory(home_centre=centres["BHY"])

    def test_cap_is_configurable(self, centres):
        s = SiteSettings.load()
        s.max_active_employees = 2
        s.save()
        UserFactory.create_batch(2, home_centre=centres["ARP"])
        with pytest.raises(ValidationError, match=r"limit \(2\)"):
            UserFactory(home_centre=centres["ARP"])

    def test_employee_requires_home_centre(self):
        form = UserForm(data={"username": "nohome", "role": "EMPLOYEE", "password": "Very-Long-Pass-123", "is_active": True})
        assert not form.is_valid()
        assert "home_centre" in form.errors


class TestAuth:
    def test_login_with_phone(self, client, centres):
        UserFactory(username="ravi", phone="9876543210", home_centre=centres["ARP"])
        resp = client.post(reverse("accounts:login"), {"username": "9876543210", "password": "s3cure-Passw0rd!"})
        assert resp.status_code == 302
        assert AuditLog.objects.filter(action="LOGIN").exists()

    def test_forced_password_change_redirect(self, client, centres):
        user = UserFactory(home_centre=centres["ARP"], must_change_password=True)
        client.force_login(user)
        resp = client.get(reverse("patients:list"))
        assert resp.status_code == 302 and resp.url == reverse("accounts:password_change")

    def test_anonymous_redirected_to_login(self, client):
        resp = client.get(reverse("patients:list"))
        assert resp.status_code == 302 and reverse("accounts:login") in resp.url

    def test_password_min_length_is_10(self, centres):
        form = UserForm(data={"username": "short", "role": "EMPLOYEE", "home_centre": centres["ARP"].pk,
                              "password": "Abc12345!", "is_active": True})
        assert not form.is_valid() and "password" in form.errors

    def test_employee_cannot_manage_users(self, client, centres):
        client.force_login(UserFactory(home_centre=centres["ARP"]))
        assert client.get(reverse("accounts:user_list")).status_code == 403


class TestAudit:
    def test_field_level_diff_logged(self, centres):
        c = centres["BHY"]
        c.address = "New address"
        c.save()
        log = AuditLog.objects.filter(action="UPDATE", object_id=str(c.pk)).latest("timestamp")
        assert log.changes["address"] == ["", "New address"]

    def test_soft_delete_logged(self, centres):
        u = UserFactory(home_centre=centres["ARP"])
        u.soft_delete()
        assert AuditLog.objects.filter(action="SOFT_DELETE", object_id=str(u.pk)).exists()
        assert User.objects.filter(pk=u.pk).exists()  # never hard-deleted
