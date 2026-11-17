from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.mixins import AdminRequiredMixin, SimpleFormPageMixin, admin_required

from .forms import ForcedPasswordChangeForm, LoginForm, UserForm
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
        return ctx


class UserCreateView(AdminRequiredMixin, SimpleFormPageMixin, CreateView):
    page_heading = "New user"
    help_note = "Max 3 active Admins. Employees count towards the employee cap set in Settings."
    model = User
    form_class = UserForm
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User created. Share the temporary password securely.")
        return super().form_valid(form)


class UserUpdateView(AdminRequiredMixin, SimpleFormPageMixin, UpdateView):
    model = User
    form_class = UserForm
    success_url = reverse_lazy("accounts:user_list")

    def get_queryset(self):
        return User.objects.filter(deleted_at__isnull=True)

    def form_valid(self, form):
        messages.success(self.request, "User updated.")
        return super().form_valid(form)


@require_POST
@admin_required
def user_soft_delete(request, pk):
    user = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    if user == request.user:
        messages.error(request, "You cannot remove your own account.")
    else:
        user.soft_delete(by=request.user)
        messages.success(request, f"{user} has been deactivated and removed.")
    return redirect("accounts:user_list")


@require_POST
@admin_required
def user_unlock(request, pk):
    from axes.utils import reset

    user = get_object_or_404(User, pk=pk)
    reset(username=user.username)
    if user.phone:
        reset(username=user.phone)
    messages.success(request, f"Login lock cleared for {user}.")
    return redirect("accounts:user_list")
