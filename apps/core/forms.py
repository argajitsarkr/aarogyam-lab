from django import forms


def style_widgets(fields):
    for f in fields.values():
        w = f.widget
        if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
            w.attrs.setdefault("class", "rounded border-slate-300 text-teal-700")
            continue
        if isinstance(w, forms.DateInput) and not isinstance(w, forms.DateTimeInput):
            w.input_type = "date"
            w.format = "%Y-%m-%d"
        css = w.attrs.get("class", "")
        if "input" not in css.split():
            w.attrs["class"] = (css + " input").strip()


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self.fields)


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass
