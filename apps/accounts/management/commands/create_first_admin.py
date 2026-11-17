import getpass
import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the first Admin account. Reads ADMIN_USERNAME / ADMIN_PASSWORD env vars or prompts."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--phone")
        parser.add_argument("--noinput", action="store_true")

    def handle(self, *args, **opts):
        username = opts["username"] or os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")
        if not username and not opts["noinput"]:
            username = input("Admin username: ").strip()
        if not password and not opts["noinput"]:
            password = getpass.getpass("Password (min 12 chars): ")
        if not username or not password:
            raise CommandError("Username and password are required.")
        if len(password) < 12:
            raise CommandError("Password must be at least 12 characters.")
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User '{username}' already exists — nothing to do.")
            return
        user = User(username=username, role=User.Role.ADMIN, is_staff=True, is_superuser=True,
                    phone=opts["phone"] or None, must_change_password=True,
                    email=username if "@" in username else "")
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Admin '{username}' created. They must change password on first login."))
