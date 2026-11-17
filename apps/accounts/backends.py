from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameBackend(ModelBackend):
    """Log in with the username (named logins use the person's email as username),
    case-insensitively - the TGMA model. Phone numbers are not login names."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        try:
            user = User.objects.get(username__iexact=username.strip())
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)  # equalise timing
            return None
        if user.check_password(password) and self.user_can_authenticate(user) and not user.deleted_at:
            return user
        return None
