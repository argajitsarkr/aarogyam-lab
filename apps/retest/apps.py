from django.apps import AppConfig


class RetestConfig(AppConfig):
    name = "apps.retest"
    label = "retest"

    def ready(self):
        from apps.audit.registry import register
        from apps.patients.services import visit_registered

        from .services import mark_conversions

        def _convert(sender, visit, **kwargs):
            mark_conversions(visit)

        visit_registered.connect(_convert, weak=False, dispatch_uid="retest_mark_conversions")
        register(self.get_model("CallLog"))
        register(self.get_model("RetestCandidate"), exclude=("priority_score", "last_called_at", "attempts"))
