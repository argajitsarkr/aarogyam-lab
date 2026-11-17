from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.mixins import AdminRequiredMixin, SimpleFormPageMixin

from .forms import CentreForm
from .models import Centre


class CentreListView(AdminRequiredMixin, ListView):
    model = Centre
    template_name = "centres/list.html"

    def get_queryset(self):
        return Centre.objects.select_related("in_charge").all()


class CentreCreateView(AdminRequiredMixin, SimpleFormPageMixin, CreateView):
    page_heading = "New centre"
    model = Centre
    form_class = CentreForm
    success_url = reverse_lazy("centres:list")

    def form_valid(self, form):
        messages.success(self.request, "Centre created.")
        return super().form_valid(form)


class CentreUpdateView(AdminRequiredMixin, SimpleFormPageMixin, UpdateView):
    model = Centre
    form_class = CentreForm
    success_url = reverse_lazy("centres:list")

    def form_valid(self, form):
        messages.success(self.request, "Centre updated.")
        return super().form_valid(form)
