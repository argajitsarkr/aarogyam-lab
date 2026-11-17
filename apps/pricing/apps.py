from django.apps import AppConfig


class PricingConfig(AppConfig):
    name = "apps.pricing"
    label = "pricing"

    def ready(self):
        from apps.audit.registry import register

        register(self.get_model("Competitor"))
        register(self.get_model("CompetitorPrice"))
