from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from apps.core.validators import normalize_phone


class UsernameOrPhoneBackend(ModelBackend):
    """Log in with either username or 10-digit phone number."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        phone = normalize_phone(username)
        try:
            user = User.objects.get(Q(username__iexact=username) | Q(phone=phone) if phone else Q(username__iexact=username))
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)  # equalise timing
            return None
        if user.check_password(password) and self.user_can_authenticate(user) and not user.deleted_at:
            return user
        return None
