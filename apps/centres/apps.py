from django.apps import AppConfig


class CentresConfig(AppConfig):
    name = "apps.centres"
    label = "centres"

    def ready(self):
        from apps.audit.registry import register

        register(self.get_model("Centre"))
