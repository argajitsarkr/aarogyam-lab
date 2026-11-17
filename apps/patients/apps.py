from django.apps import AppConfig


class PatientsConfig(AppConfig):
    name = "apps.patients"
    label = "patients"

    def ready(self):
        from apps.audit.registry import register

        for name in ("Patient", "Visit", "VisitTest", "Doctor", "TestCatalog"):
            register(self.get_model(name))
