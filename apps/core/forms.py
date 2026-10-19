import time

from django import forms
from django.core import signing

from .forms_base import BaseForm, BaseModelForm
from .models import ContactMessage, SiteSettings


class SiteSettingsForm(BaseModelForm):
    class Meta:
        model = SiteSettings
        exclude = ["updated_at", "demo_data_loaded"]
        widgets = {
            "banner_text": forms.Textarea(attrs={"rows": 3}),
            "intro_text": forms.Textarea(attrs={"rows": 4}),
            "program_text": forms.Textarea(attrs={"rows": 4}),
            "admission_text": forms.Textarea(attrs={"rows": 4}),
            "color_primary": forms.TextInput(attrs={"type": "color"}),
            "color_accent": forms.TextInput(attrs={"type": "color"}),
            "color_secondary": forms.TextInput(attrs={"type": "color"}),
            "color_dark": forms.TextInput(attrs={"type": "color"}),
        }

    def clean_map_embed_url(self):
        url = self.cleaned_data.get("map_embed_url", "")
        if url and not url.startswith(("https://www.google.com/maps/embed", "https://maps.google.com/maps")):
            raise forms.ValidationError("Chỉ chấp nhận đường dẫn nhúng của Google Maps (https://www.google.com/maps/embed?...).")
        return url


class ContactForm(BaseModelForm):
    """Biểu mẫu liên hệ có chống spam: trường bẫy (honeypot) + kiểm tra thời gian điền + giới hạn tần suất."""

    website = forms.CharField(required=False, label="Để trống trường này",
                              widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}))
    ts = forms.CharField(widget=forms.HiddenInput)
    agree = forms.BooleanField(label="Tôi đồng ý để nhà trường sử dụng thông tin trên để phản hồi liên hệ này.")

    MIN_SECONDS = 3

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5, "maxlength": 3000})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["ts"] = signing.dumps(time.time())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise forms.ValidationError("Không gửi được biểu mẫu.")
        try:
            started = signing.loads(self.data.get("ts", ""), max_age=3600)
        except signing.BadSignature:
            raise forms.ValidationError("Biểu mẫu đã hết hạn, vui lòng tải lại trang.")
        if time.time() - float(started) < self.MIN_SECONDS:
            raise forms.ValidationError("Bạn gửi quá nhanh, vui lòng thử lại.")
        if not cleaned.get("email") and not cleaned.get("phone"):
            raise forms.ValidationError("Vui lòng để lại email hoặc số điện thoại để nhà trường phản hồi.")
        return cleaned


class ContactStatusForm(BaseModelForm):
    class Meta:
        model = ContactMessage
        fields = ["status", "note"]


class AuditFilterForm(BaseForm):
    q = forms.CharField(label="Tìm", required=False)
    date_from = forms.DateField(label="Từ ngày", required=False)
    date_to = forms.DateField(label="Đến ngày", required=False)
