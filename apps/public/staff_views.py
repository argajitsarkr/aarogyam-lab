"""The staff queue for public-site enquiries, at /staff/enquiries/.

Enquiries arrive from strangers, so there is nothing to centre-scope on yet: an
enquiry with no centre belongs to whoever picks it up, exactly like the re-test
call pool. An enquiry that named a centre is still visible to everyone, because
the front desk that answers the phone is not always the one the person chose.
"""
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView

from .models import Enquiry
from .staff_forms import EnquiryHandleForm


class EnquiryListView(LoginRequiredMixin, ListView):
    template_name = "enquiries/list.html"
    context_object_name = "enquiries"
    paginate_by = 25
    results_label = "enquiries"

    def get_queryset(self):
        qs = Enquiry.objects.select_related("centre", "test", "handled_by")
        self.status = self.request.GET.get("status") or "OPEN"
        self.kind = self.request.GET.get("kind") or ""
        if self.status == "OPEN":
            qs = qs.filter(status__in=[Enquiry.Status.NEW, Enquiry.Status.CONTACTED])
        elif self.status != "ALL":
            qs = qs.filter(status=self.status)
        if self.kind:
            qs = qs.filter(kind=self.kind)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["results_label"] = self.results_label
        ctx["active_status"] = self.status
        ctx["active_kind"] = self.kind
        ctx["kind_choices"] = Enquiry.Kind.choices
        # "Open" is first and is the default: an unanswered enquiry is the only
        # state that needs anyone's attention.
        ctx["status_links"] = [("OPEN", "Open"), *Enquiry.Status.choices, ("ALL", "All")]
        ctx["new_count"] = Enquiry.objects.filter(status=Enquiry.Status.NEW).count()
        return ctx


class EnquiryDetailView(LoginRequiredMixin, DetailView):
    model = Enquiry
    template_name = "enquiries/detail.html"
    context_object_name = "enquiry"

    def get_queryset(self):
        return Enquiry.objects.select_related("centre", "test", "handled_by")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", EnquiryHandleForm(instance=self.object))
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = EnquiryHandleForm(request.POST, instance=self.object)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        enquiry = form.save(commit=False)
        if enquiry.status != Enquiry.Status.NEW and not enquiry.handled_at:
            enquiry.handled_by = request.user
            enquiry.handled_at = timezone.now()
        enquiry.save()
        messages.success(request, f"Enquiry marked {enquiry.get_status_display().lower()}.")
        return redirect("enquiries:detail", pk=enquiry.pk)


def prescription_download(request, pk):
    """Serves an uploaded prescription to signed-in staff only.

    The file lives in PRIVATE_MEDIA_ROOT, outside the web root, so there is no
    url that reaches it directly. In production nginx does the sending via
    X-Accel-Redirect (the `/_protected/` internal location); the dev server has
    no such thing, so it streams the file itself.
    """
    if not request.user.is_authenticated:
        raise Http404
    enquiry = get_object_or_404(Enquiry, pk=pk)
    if not enquiry.prescription:
        raise Http404("No prescription on this enquiry")

    name = enquiry.prescription.name
    filename = Path(name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    if settings.DEBUG:
        return FileResponse(enquiry.prescription.open("rb"), content_type=content_type, filename=filename)

    response = HttpResponse(status=200)
    response["X-Accel-Redirect"] = f"/_protected/{name}"
    response["Content-Type"] = content_type
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
