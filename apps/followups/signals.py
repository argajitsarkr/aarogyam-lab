import datetime as dt

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.patients.models import VisitTest
from apps.patients.services import visit_registered

from .services import auto_close_on_visit, create_abnormal_followup

ABNORMAL_LOOKBACK_DAYS = 30  # don't spam follow-ups for imported historical results


@receiver(post_save, sender=VisitTest)
def abnormal_result_followup(sender, instance, raw=False, **kwargs):
    if raw or instance.flag != VisitTest.Flag.ABNORMAL:
        return
    ref = instance.report_date or timezone.localdate()
    if ref < timezone.localdate() - dt.timedelta(days=ABNORMAL_LOOKBACK_DAYS):
        return
    create_abnormal_followup(instance)


@receiver(visit_registered)
def close_followups(sender, visit, **kwargs):
    auto_close_on_visit(visit)
