import logging

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.core.files.storage import FileSystemStorage

logger = logging.getLogger(__name__)


def private_storage():
    """File storage rooted OUTSIDE the web root; files are only reachable via
    authenticated, centre-scoped download views. (Callable so migrations stay
    environment-independent.)"""
    return FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT), base_url=None)


class ForgivingManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Hashed static filenames, where a broken reference degrades instead of exploding.

    ManifestStaticFilesStorage rewrites every `url()` inside CSS to the hashed name of
    the file it points at. Vendored stylesheets often reference something they do not
    ship - an optional sprite, a source map, an icon for a feature we never use - and
    the default raises ValueError, which fails `collectstatic` and so fails the whole
    deploy.

    `manifest_strict = False` does NOT cover this: it only softens lookups at request
    time, not the rewrite during collectstatic. So `hashed_name` is overridden to log
    the dead reference and leave the original url alone. SuspiciousFileOperation is
    caught alongside ValueError, because a reference that climbs out of the static
    root (`../../something.css`) raises that instead.
    """

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except (ValueError, SuspiciousFileOperation) as exc:
            logger.warning("static: leaving an unhashed reference in place - %s", exc)
            return name
