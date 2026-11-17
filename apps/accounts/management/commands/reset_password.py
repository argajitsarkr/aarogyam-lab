import secrets

from axes.utils import reset
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import log_event


class Command(BaseCommand):
    help = (
        "Give one account a new one-time password (printed once, here only), force a change at "
        "next login and clear any lock. Server-side replacement for TGMA's one-off reset."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **opts):
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            raise CommandError(f"No account '{username}'.")
        temp = secrets.token_urlsafe(12)  # 16 chars
        user.set_password(temp)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        reset(username=user.username)
        log_event(AuditLog.Action.UPDATE, obj=user, note="password reset on server (reset_password)")
        self.stdout.write(f"One-time password for {user.username}:\n\n    {temp}\n")
        self.stdout.write("Give it to them privately. They must set their own at next login.")
