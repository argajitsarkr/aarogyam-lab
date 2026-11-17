import datetime as dt
import decimal
import uuid

from django.contrib.contenttypes.models import ContentType
from django.db.models.fields.files import FieldFile

from apps.core.threadlocal import get_client_ip, get_current_request, get_current_user


def serialize_value(value):
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, FieldFile):
        return value.name or None
    if isinstance(value, (list, dict, str, int, float, bool)) or value is None:
        return value
    return str(value)


def _centre_for(obj, user):
    for attr in ("centre_id", "registered_at_centre_id", "home_centre_id"):
        val = getattr(obj, attr, None) if obj is not None else None
        if val:
            return val
    if obj is not None and obj.__class__.__name__ == "Centre":
        return obj.pk
    return getattr(user, "home_centre_id", None) if user else None


def log_event(action, obj=None, user=None, request=None, centre_id=None, changes=None, note=""):
    from .models import AuditLog

    request = request or get_current_request()
    if user is None:
        user = get_current_user()
    if user is not None and not getattr(user, "pk", None):
        user = None
    return AuditLog.objects.create(
        action=action,
        user=user,
        centre_id=centre_id or _centre_for(obj, user),
        ip_address=get_client_ip(request),
        content_type=ContentType.objects.get_for_model(obj) if obj is not None else None,
        object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
        object_repr=str(obj)[:255] if obj is not None else "",
        changes=changes or {},
        note=note[:500],
    )
