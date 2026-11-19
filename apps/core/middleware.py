from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .scoping import resolve_scope
from .threadlocal import set_current_request

# The staff half of the site. Every path under one of these needs a session;
# everything else is the public site and is open. The login page and the lockout
# notice sit inside /accounts/ but have to stay reachable without one.
STAFF_URL_PREFIX = "/staff/"
LOGIN_REQUIRED_PREFIXES = (STAFF_URL_PREFIX, "/accounts/", "/system-admin/")
OPEN_PREFIXES = ("/accounts/login/", "/accounts/locked/")


class HealthCheckMiddleware:
    """Answers GET /healthz with a plain 200 before host validation and the HTTPS
    redirect, so the container healthcheck works whatever ALLOWED_HOSTS holds.
    Must be first in MIDDLEWARE. Reveals nothing; nginx does not expose it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            from django.http import HttpResponse

            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)


class RequestContextMiddleware:
    """Stores the request in a thread-local (for audit signals) and attaches
    a lazily-resolved `request.scope`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        request.scope = SimpleLazyObject(lambda: resolve_scope(request.user))
        try:
            return self.get_response(request)
        finally:
            set_current_request(None)


def is_staff_area(path):
    """True for the staff half of the site: the pages that need a session and
    must never be indexed. The public site is everything else."""
    return path.startswith(LOGIN_REQUIRED_PREFIXES) and not path.startswith(OPEN_PREFIXES)


class LoginRequiredMiddleware:
    """Guards the staff half of the site. The public pages are open."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and is_staff_area(request.path):
            if request.headers.get("HX-Request"):
                from django.http import HttpResponse

                resp = HttpResponse(status=401)
                resp["HX-Redirect"] = reverse(settings.LOGIN_URL)
                return resp
            return redirect(f"{reverse(settings.LOGIN_URL)}?next={request.get_full_path()}")
        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """Users flagged with must_change_password can only reach the change page."""

    allowed = ("/accounts/password/", "/accounts/logout/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, "must_change_password", False):
            if not request.path.startswith(self.allowed):
                return redirect("accounts:password_change")
        return self.get_response(request)


class NoIndexMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if is_staff_area(request.path) or request.path.startswith("/accounts/"):
            # Patient data and the sign-in screen: never indexed, never cached.
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            response.setdefault("Cache-Control", "private, no-store")
        return response
