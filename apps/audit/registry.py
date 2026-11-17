"""Models registered here get automatic field-level audit logging."""

_registry = {}


def register(model, exclude=()):
    _registry[model] = set(exclude) | {"updated_at", "last_login", "password", "ui_preferences"}
    return model


def get_excluded(model):
    return _registry.get(model)


def registered_models():
    return list(_registry)
