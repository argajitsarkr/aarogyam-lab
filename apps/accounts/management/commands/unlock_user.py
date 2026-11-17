from axes.utils import reset
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Clear the 15-minute login lock for one account (server-side, as on TGMA)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **opts):
        if not User.objects.filter(username__iexact=username).exists():
            raise CommandError(f"No account '{username}'.")
        cleared = reset(username=username)
        self.stdout.write(self.style.SUCCESS(f"Unlocked {username} ({cleared} lock record(s) cleared)."))
