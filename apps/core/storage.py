from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    """File storage rooted OUTSIDE the web root; files are only reachable via
    authenticated, centre-scoped download views. (Callable so migrations stay
    environment-independent.)"""
    return FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT), base_url=None)
