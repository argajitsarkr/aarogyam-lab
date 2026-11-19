"""The public site.

Nothing here is centre-scoped, because nothing here is patient data: it reads
the published slice of the catalogue (`is_public`) and writes exactly one kind
of row, an `Enquiry`. Every page is anonymous, so every query must be cheap.
"""
from django.contrib import messages
from django.db.models import Min, Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.centres.models import Centre
from apps.patients.models import TestCatalog
from apps.pricing.models import CompetitorPrice

from .forms import EnquiryForm
from .models import Banner, Doctor, Enquiry, HealthConcern, MedicineCategory


def public_tests():
    return TestCatalog.objects.filter(is_active=True, is_public=True)


def with_partner_prices(queryset):
    """Each test carries every partner's price, cheapest first.

    The lab takes a commission and the customer picks the partner, so the page
    lists them side by side with no "our price" column and no cheapest-wins
    badge - see the pricing rule in CLAUDE.md.
    """
    return queryset.prefetch_related(
        Prefetch(
            "competitor_prices",
            queryset=CompetitorPrice.objects.select_related("competitor")
            .filter(competitor__is_active=True)
            .order_by("price"),
        )
    ).annotate(from_price=Min("competitor_prices__price")).order_by("name")


class PublicPageMixin:
    """Marks the request so the nav context processor fires, and hands the
    template the enquiry form every call-to-action posts."""

    page_name = ""

    def setup(self, request, *args, **kwargs):
        request.is_public_page = True
        super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("enquiry_form", EnquiryForm(initial={"kind": Enquiry.Kind.CALLBACK}))
        ctx["page_name"] = self.page_name
        return ctx


class HomeView(PublicPageMixin, TemplateView):
    template_name = "public/home.html"
    page_name = "home"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["banners"] = Banner.objects.published()[:6]
        ctx["concerns"] = HealthConcern.objects.published()[:8]
        ctx["centres"] = Centre.objects.filter(is_active=True, is_public=True)
        ctx["doctors"] = Doctor.objects.published().prefetch_related("centres")[:4]
        ctx["popular_tests"] = with_partner_prices(public_tests())[:6]
        ctx["medicine_categories"] = MedicineCategory.objects.published()[:6]
        return ctx


class CentreListView(PublicPageMixin, ListView):
    template_name = "public/centres.html"
    context_object_name = "centres"
    page_name = "centres"

    def get_queryset(self):
        return Centre.objects.filter(is_active=True, is_public=True).prefetch_related("doctors")


class CentreDetailView(PublicPageMixin, DetailView):
    template_name = "public/centre_detail.html"
    context_object_name = "centre"
    page_name = "centres"

    def get_object(self, queryset=None):
        code = (self.kwargs["slug"] or "").upper()
        try:
            return Centre.objects.prefetch_related("doctors").get(
                short_code=code, is_active=True, is_public=True
            )
        except Centre.DoesNotExist:
            raise Http404("No such centre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["enquiry_form"] = EnquiryForm(
            initial={"kind": Enquiry.Kind.CALLBACK, "centre": self.object.pk}
        )
        return ctx


class DoctorListView(PublicPageMixin, ListView):
    template_name = "public/doctors.html"
    context_object_name = "doctors"
    page_name = "doctors"

    def get_queryset(self):
        return Doctor.objects.published().prefetch_related("centres")


class TestListView(PublicPageMixin, ListView):
    template_name = "public/tests.html"
    context_object_name = "tests"
    paginate_by = 24
    page_name = "tests"

    def get_queryset(self):
        qs = with_partner_prices(public_tests())
        self.query = (self.request.GET.get("q") or "").strip()
        self.category = self.request.GET.get("category") or ""
        if self.query:
            qs = qs.filter(name__icontains=self.query)
        if self.category:
            qs = qs.filter(category=self.category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        used = set(public_tests().values_list("category", flat=True))
        ctx["categories"] = [c for c in TestCatalog.Category.choices if c[0] in used]
        ctx["query"] = self.query
        ctx["active_category"] = self.category
        ctx["banners"] = Banner.objects.published()[:6]
        ctx["concerns"] = HealthConcern.objects.published()[:8]
        return ctx


class TestDetailView(PublicPageMixin, DetailView):
    template_name = "public/test_detail.html"
    context_object_name = "test"
    page_name = "tests"

    def get_object(self, queryset=None):
        try:
            return with_partner_prices(public_tests()).get(code__iexact=self.kwargs["code"])
        except TestCatalog.DoesNotExist:
            raise Http404("No such test")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["enquiry_form"] = EnquiryForm(
            initial={"kind": Enquiry.Kind.TEST, "test": self.object.pk}
        )
        ctx["related"] = (
            with_partner_prices(public_tests())
            .filter(category=self.object.category)
            .exclude(pk=self.object.pk)[:4]
        )
        return ctx


class ConcernView(PublicPageMixin, DetailView):
    template_name = "public/concern.html"
    context_object_name = "concern"
    page_name = "tests"

    def get_object(self, queryset=None):
        try:
            return HealthConcern.objects.published().get(slug=self.kwargs["slug"])
        except HealthConcern.DoesNotExist:
            raise Http404("No such health concern")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tests"] = with_partner_prices(self.object.tests.filter(is_active=True, is_public=True))
        return ctx


class MedicineHomeView(PublicPageMixin, ListView):
    template_name = "public/medicines.html"
    context_object_name = "categories"
    page_name = "medicines"

    def get_queryset(self):
        return MedicineCategory.objects.published()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["enquiry_form"] = EnquiryForm(initial={"kind": Enquiry.Kind.MEDICINE})
        return ctx


class MedicineCategoryView(PublicPageMixin, DetailView):
    template_name = "public/medicine_category.html"
    context_object_name = "category"
    page_name = "medicines"

    def get_object(self, queryset=None):
        try:
            return MedicineCategory.objects.published().get(slug=self.kwargs["slug"])
        except MedicineCategory.DoesNotExist:
            raise Http404("No such category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["enquiry_form"] = EnquiryForm(initial={"kind": Enquiry.Kind.MEDICINE})
        ctx["other_categories"] = MedicineCategory.objects.published().exclude(pk=self.object.pk)[:6]
        return ctx


class PrescriptionUploadView(PublicPageMixin, TemplateView):
    template_name = "public/prescription.html"
    page_name = "medicines"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["enquiry_form"] = EnquiryForm(initial={"kind": Enquiry.Kind.PRESCRIPTION})
        return ctx


class AboutView(PublicPageMixin, TemplateView):
    template_name = "public/about.html"
    page_name = "about"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["centres"] = Centre.objects.filter(is_active=True, is_public=True)
        ctx["doctor_count"] = Doctor.objects.published().count()
        ctx["test_count"] = public_tests().count()
        return ctx


class ContactView(PublicPageMixin, TemplateView):
    template_name = "public/contact.html"
    page_name = "contact"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["centres"] = Centre.objects.filter(is_active=True, is_public=True)
        return ctx


def client_ip(request):
    # Behind the Cloudflare tunnel nginx forwards the real address in
    # CF-Connecting-IP; X-Forwarded-For is the fallback for a direct proxy.
    for header in ("CF-Connecting-IP", "X-Forwarded-For"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class EnquiryCreateView(PublicPageMixin, FormView):
    """The one write the public site can make. Posted by every call-to-action;
    answers HTMX with a panel and a plain browser with a redirect + message."""

    form_class = EnquiryForm
    template_name = "public/_enquiry_form.html"

    def form_valid(self, form):
        enquiry = form.save(commit=False)
        enquiry.client_ip = client_ip(self.request)
        if form.looks_like_spam:
            # Kept, not dropped: a wrongly-flagged person is still reachable.
            enquiry.status = Enquiry.Status.SPAM
        enquiry.save()
        if self.request.headers.get("HX-Request"):
            return self.render_to_response({"submitted": enquiry, "enquiry_form": form})
        messages.success(self.request, "Thank you. We will call you back shortly.")
        return redirect(self.request.POST.get("next") or reverse("public:home"))

    def form_invalid(self, form):
        # htmx: swap the form for itself with the errors in place. A 4xx body is
        # ignored by htmx unless configured, so this answers 200 on purpose.
        if self.request.headers.get("HX-Request"):
            return self.render_to_response({"enquiry_form": form})

        # No JavaScript: send them back to the page they posted from with the
        # errors as messages. Rendering this partial on its own would give them
        # a bare, header-less page, and FormView's own form_invalid would hand
        # the template a fresh unbound form - losing the errors entirely.
        for field, errors in form.errors.items():
            label = form.fields[field].label if field in form.fields else ""
            for error in errors:
                messages.error(self.request, f"{label}: {error}" if label else error)
        return redirect(self.request.POST.get("next") or reverse("public:home"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # PublicPageMixin seeds a blank form for the call-to-action includes;
        # here the bound one, with its errors, is the thing to render.
        if ctx.get("form") is not None:
            ctx["enquiry_form"] = ctx["form"]
        return ctx

    def get(self, request, *args, **kwargs):
        return HttpResponse(status=405)
