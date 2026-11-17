"""Holds the current request so model signals (audit log) can see the user/IP."""
import threading

_state = threading.local()


def set_current_request(request):
    _state.request = request


def get_current_request():
    return getattr(_state, "request", None)


def get_current_user():
    request = get_current_request()
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return None


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
