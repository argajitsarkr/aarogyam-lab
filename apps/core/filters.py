import django_filters

from .forms import style_widgets


class StyledFilterSet(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self.form.fields)
