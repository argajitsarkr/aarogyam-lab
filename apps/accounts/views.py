from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.views.generic import ListView

from apps.core.mixins import AdminRequiredMixin

from .forms import ForcedPasswordChangeForm, LoginForm
from .models import User


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.get_user()
        if user.must_change_password:
            messages.warning(self.request, "Please set a new password before continuing.")
        else:
            messages.success(self.request, f"Welcome, {user.get_full_name() or user.username}.")
        return response


class LogoutView(auth_views.LogoutView):
    """POST-only logout (Django default) that confirms on the login page, as TGMA does."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have been logged out.")
        return response


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = ForcedPasswordChangeForm
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        from apps.audit.models import AuditLog
        from apps.audit.services import log_event

        was_forced = self.request.user.must_change_password
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        log_event(AuditLog.Action.PASSWORD_CHANGED, user=form.user, request=self.request, obj=form.user,
                  note="first-login change" if was_forced else "")
        messages.success(self.request, "Password updated.")
        return response


class UserListView(AdminRequiredMixin, ListView):
    """Read-only. Accounts are created, changed, unlocked and reset on the server
    (seed_users / unlock_user / reset_password commands), as on TGMA."""

    template_name = "accounts/user_list.html"

    def get_queryset(self):
        return User.objects.filter(deleted_at__isnull=True).select_related("home_centre").prefetch_related("extra_centres").order_by("role", "home_centre__name", "username")

    def get_context_data(self, **kwargs):
        from apps.core.models import SiteSettings
        from django.conf import settings

        ctx = super().get_context_data(**kwargs)
        ctx["admin_count"] = User.objects.active_admins().count()
        ctx["employee_count"] = User.objects.active_employees().count()
        ctx["admin_cap"] = settings.MAX_ACTIVE_ADMINS
        ctx["employee_cap"] = SiteSettings.load().max_active_employees
        ctx["locked_usernames"] = locked_usernames()
        return ctx


def locked_usernames():
    """Usernames currently locked out by django-axes (failure limit reached within the cool-off)."""
    from datetime import timedelta

    from axes.models import AccessAttempt
    from django.conf import settings
    from django.utils import timezone

    since = timezone.now() - timedelta(hours=float(settings.AXES_COOLOFF_TIME))
    return {
        name.lower() for name in AccessAttempt.objects.filter(
            failures_since_start__gte=settings.AXES_FAILURE_LIMIT, attempt_time__gte=since,
        ).values_list("username", flat=True) if name
    }
