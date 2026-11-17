from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .scoping import resolve_scope
from .threadlocal import set_current_request

PUBLIC_PATH_PREFIXES = ("/accounts/login/", "/robots.txt", "/static/")


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


class LoginRequiredMiddleware:
    """No public pages besides the login page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(PUBLIC_PATH_PREFIXES):
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
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.setdefault("Cache-Control", "private, no-store")
        response.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        return response
