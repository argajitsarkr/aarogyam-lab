from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import AuditLog
from .registry import get_excluded
from .services import log_event, serialize_value


def _field_values(instance, excluded):
    data = {}
    for f in instance._meta.concrete_fields:
        if f.name in excluded:
            continue
        data[f.name] = serialize_value(getattr(instance, f.attname))
    return data


@receiver(pre_save)
def _capture_old(sender, instance, raw=False, **kwargs):
    excluded = get_excluded(sender)
    if excluded is None or raw or not instance.pk:
        return
    try:
        old = sender._base_manager.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance._audit_old = _field_values(old, excluded)


@receiver(post_save)
def _log_save(sender, instance, created, raw=False, **kwargs):
    excluded = get_excluded(sender)
    if excluded is None or raw:
        return
    new = _field_values(instance, excluded)
    if created:
        log_event(AuditLog.Action.CREATE, obj=instance, changes={k: [None, v] for k, v in new.items() if v not in (None, "")})
        return
    old = getattr(instance, "_audit_old", {})
    diff = {k: [old.get(k), v] for k, v in new.items() if old.get(k) != v}
    if not diff:
        return
    action = AuditLog.Action.UPDATE
    if "deleted_at" in diff and diff["deleted_at"][0] is None and diff["deleted_at"][1]:
        action = AuditLog.Action.SOFT_DELETE
    log_event(action, obj=instance, changes=diff)
    instance._audit_old = new


@receiver(post_delete)
def _log_delete(sender, instance, **kwargs):
    excluded = get_excluded(sender)
    if excluded is None:
        return
    log_event(AuditLog.Action.DELETE, obj=instance, changes={k: [v, None] for k, v in _field_values(instance, excluded).items()})


@receiver(user_logged_in)
def _logged_in(sender, request, user, **kwargs):
    log_event(AuditLog.Action.LOGIN, user=user, request=request, obj=user)


@receiver(user_logged_out)
def _logged_out(sender, request, user, **kwargs):
    if user:
        log_event(AuditLog.Action.LOGOUT, user=user, request=request, obj=user)


def _failure_reason(username):
    """Why a login failed, for the audit log only (the user always sees the same
    generic message, so this never helps anyone enumerate accounts). As on TGMA."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(username__iexact=username.strip()).first()
    if user is None:
        return "unknown user"
    if not user.is_active or user.deleted_at:
        return "inactive account"
    return "bad password"


@receiver(user_login_failed)
def _login_failed(sender, credentials, request=None, **kwargs):
    from axes.handlers.proxy import AxesProxyHandler

    username = str(credentials.get("username", ""))[:50]
    if request is not None and AxesProxyHandler.is_locked(request, credentials):
        # Attempt against an account that is already locked: the password was not checked.
        log_event(AuditLog.Action.LOGIN_BLOCKED, request=request, note=f"username={username}; account locked")
        return
    log_event(AuditLog.Action.LOGIN_FAILED, request=request, note=f"username={username}; {_failure_reason(username)}")
