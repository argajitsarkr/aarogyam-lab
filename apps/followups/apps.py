from django.apps import AppConfig


class FollowupsConfig(AppConfig):
    name = "apps.followups"
    label = "followups"

    def ready(self):
        from apps.audit.registry import register

        from . import signals  # noqa: F401

        register(self.get_model("FollowUp"))
