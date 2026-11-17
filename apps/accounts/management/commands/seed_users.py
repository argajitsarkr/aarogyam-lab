import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.seed_users import REMOVE_USERS, SEED_USERS
from apps.centres.models import Centre


class Command(BaseCommand):
    help = (
        "Create/update lab accounts from apps/accounts/seed_users.py (TGMA init_db.py model). "
        "Bootstrap passwords come from the SEED_PW_* variables in .env. Idempotent; never "
        "re-enables a deactivated account and never changes an existing password unless "
        "--reset-passwords is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords", action="store_true",
            help="Also reset EXISTING accounts to their SEED_PW_* value (must change at next login) and unlock them.",
        )

    def handle(self, *args, reset_passwords=False, **opts):
        created = updated = skipped = 0
        centres = {c.short_code: c for c in Centre.objects.all()}

        for spec in SEED_USERS:
            username = spec["username"]
            password = os.environ.get(spec["password_env"], "")
            user = User.objects.filter(username__iexact=username).first()
            is_new = user is None
            if is_new:
                if not password:
                    self.stdout.write(self.style.WARNING(
                        f"skip {username}: not created - set {spec['password_env']} in .env first"))
                    skipped += 1
                    continue
                user = User(username=username)

            user.first_name = spec.get("first_name", "")
            user.last_name = spec.get("last_name", "")
            if "@" in username:
                user.email = username
            user.role = spec["role"]
            user.home_centre = centres.get(spec.get("home_centre") or "")
            if user.role == User.Role.ADMIN:
                user.is_staff = user.is_superuser = True

            if is_new or (reset_passwords and password):
                try:
                    validate_password(password, user)
                except ValidationError as exc:
                    self.stdout.write(self.style.ERROR(
                        f"skip {username}: {spec['password_env']} rejected - {' '.join(exc.messages)}"))
                    skipped += 1
                    continue
                user.set_password(password)
                user.must_change_password = True

            try:
                user.full_clean(exclude=["password"])
                user.save()
            except ValidationError as exc:
                self.stdout.write(self.style.ERROR(f"skip {username}: {' '.join(exc.messages)}"))
                skipped += 1
                continue
            user.extra_centres.set([centres[c] for c in spec.get("extra_centres", []) if c in centres])

            if not is_new and reset_passwords and password:
                from axes.utils import reset

                reset(username=username)
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"created {username} ({user.role}) - must change password at first login"))
            else:
                updated += 1
                note = " + password reset" if reset_passwords and password else ""
                state = "" if user.is_active else " [inactive - left as is]"
                self.stdout.write(f"updated {username} ({user.role}){note}{state}")

        for username in REMOVE_USERS:
            user = User.objects.filter(username__iexact=username, deleted_at__isnull=True).first()
            if user:
                user.soft_delete()
                self.stdout.write(self.style.WARNING(f"deactivated {username}"))

        self.stdout.write(f"seed_users: {created} created, {updated} updated, {skipped} skipped")
