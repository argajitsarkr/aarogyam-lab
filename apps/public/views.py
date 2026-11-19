from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Placeholder for the public site. Phase 1 replaces this with the real
    home page; it exists now so the routing split has something at `/`."""

    template_name = "public/home.html"
