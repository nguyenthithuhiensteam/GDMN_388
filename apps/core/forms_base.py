"""Lớp form cơ sở: tự gắn class Bootstrap, định dạng ngày dd/mm/yyyy, nhận user."""
from django import forms

DATE_FORMAT = "%d/%m/%Y"
DATETIME_FORMAT = "%d/%m/%Y %H:%M"


class VNDateInput(forms.DateInput):
    def __init__(self, attrs=None):
        base = {"placeholder": "dd/mm/yyyy", "inputmode": "numeric", "autocomplete": "off", "class": "form-control"}
        base.update(attrs or {})
        super().__init__(attrs=base, format=DATE_FORMAT)


class VNDateTimeInput(forms.DateTimeInput):
    def __init__(self, attrs=None):
        base = {"placeholder": "dd/mm/yyyy hh:mm", "autocomplete": "off", "class": "form-control"}
        base.update(attrs or {})
        super().__init__(attrs=base, format=DATETIME_FORMAT)


def style_fields(form):
    for name, field in form.fields.items():
        w = field.widget
        if isinstance(field, forms.DateTimeField) and not isinstance(w, VNDateTimeInput):
            field.widget = w = VNDateTimeInput()
        elif isinstance(field, forms.DateField) and not isinstance(w, VNDateInput):
            field.widget = w = VNDateInput()
        if isinstance(w, (forms.CheckboxInput,)):
            w.attrs.setdefault("class", "form-check-input")
        elif isinstance(w, (forms.Select, forms.SelectMultiple)):
            w.attrs.setdefault("class", "form-select")
        elif isinstance(w, forms.CheckboxSelectMultiple):
            pass
        else:
            w.attrs.setdefault("class", "form-control")
        if isinstance(w, forms.Textarea):
            w.attrs.setdefault("rows", 4)


class BaseForm(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style_fields(self)


class BaseModelForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style_fields(self)
