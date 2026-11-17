from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import User


@shared_task
def send_daily_reminders():
    """Email each employee (with an email address) a digest of today's work."""
    from apps.retest.models import RetestCandidate

    from .models import FollowUp

    today = timezone.localdate()
    sent = 0
    for user in User.objects.active_employees().exclude(email=""):
        due = FollowUp.objects.open().filter(assigned_to=user, due_date__lte=today).count()
        calls = RetestCandidate.objects.open().filter(assigned_to=user).count()
        if not (due or calls):
            continue
        send_mail(
            "Aarogyam: your work for today",
            f"Hello {user.first_name or user.username},\n\nFollow-ups due/overdue: {due}\n"
            f"Re-test calls pending: {calls}\n\nPlease log in to the lab dashboard to action them.\n",
            None, [user.email], fail_silently=True,
        )
        sent += 1
    return sent
