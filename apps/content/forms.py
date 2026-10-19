from django import forms

from apps.core.forms_base import BaseForm, BaseModelForm

from .models import (
    Album, Announcement, Category, Disclosure, DisclosureSection, MediaItem, Page, Post, PublicDocument, StaffProfile,
)

RICH = forms.Textarea(attrs={"rows": 14, "class": "form-control js-rich"})


class CategoryForm(BaseModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "order"]


class PostForm(BaseModelForm):
    class Meta:
        model = Post
        fields = ["title", "category", "summary", "body", "thumbnail", "thumbnail_consent", "is_featured", "group"]
        widgets = {"body": RICH, "summary": forms.Textarea(attrs={"rows": 3})}


class AnnouncementForm(BaseModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "kind", "body", "attachment", "event_date", "start_date", "end_date", "is_pinned"]
        widgets = {"body": RICH}

    def clean(self):
        cleaned = super().clean()
        s, e = cleaned.get("start_date"), cleaned.get("end_date")
        if s and e and e < s:
            self.add_error("end_date", "Ngày hết hạn phải sau ngày bắt đầu hiển thị.")
        return cleaned


class PageForm(BaseModelForm):
    class Meta:
        model = Page
        fields = ["title", "section", "body", "image", "order"]
        widgets = {"body": RICH}


class StaffProfileForm(BaseModelForm):
    class Meta:
        model = StaffProfile
        fields = ["full_name", "position", "staff_group", "photo", "bio", "order", "public_consent", "is_visible"]


class AlbumForm(BaseModelForm):
    class Meta:
        model = Album
        fields = ["title", "kind", "school_year", "campus", "school_class", "group", "event_date", "description", "visibility"]


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"multiple": True, "accept": "image/*", "class": "form-control"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return [single(data, initial)] if data else []


class MediaUploadForm(BaseForm):
    images = MultipleImageField(label="Chọn ảnh (có thể chọn nhiều)", required=False)
    video_url = forms.URLField(label="Hoặc liên kết video YouTube", required=False)
    caption = forms.CharField(label="Chú thích chung", max_length=255, required=False)
    has_children = forms.BooleanField(label="Ảnh có hình ảnh trẻ em", required=False, initial=True)

    MAX_FILES = 30

    def clean(self):
        cleaned = super().clean()
        from apps.core.validators import validate_image_upload

        imgs = cleaned.get("images") or []
        if len(imgs) > self.MAX_FILES:
            raise forms.ValidationError(f"Tối đa {self.MAX_FILES} ảnh mỗi lần tải lên.")
        for f in imgs:
            validate_image_upload(f)
        if not imgs and not cleaned.get("video_url"):
            raise forms.ValidationError("Hãy chọn ít nhất một ảnh hoặc nhập liên kết video.")
        url = cleaned.get("video_url")
        if url and not any(h in url for h in ("youtube.com/", "youtu.be/")):
            self.add_error("video_url", "Chỉ hỗ trợ liên kết YouTube.")
        return cleaned


class MediaItemForm(BaseModelForm):
    class Meta:
        model = MediaItem
        fields = ["caption", "has_children", "order"]


class ConsentForm(BaseForm):
    consent_status = forms.ChoiceField(label="Quyền sử dụng hình ảnh", choices=MediaItem.CONSENT_CHOICES)
    consent_note = forms.CharField(label="Căn cứ xác nhận", max_length=255, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("consent_status") == MediaItem.CONSENT_APPROVED and not cleaned.get("consent_note"):
            self.add_error("consent_note", "Cần ghi căn cứ xác nhận (ví dụ: phiếu đồng ý của cha mẹ trẻ).")
        return cleaned


class PublicDocumentForm(BaseModelForm):
    class Meta:
        model = PublicDocument
        fields = ["title", "category", "description", "file"]


class DisclosureSectionForm(BaseModelForm):
    class Meta:
        model = DisclosureSection
        fields = ["name", "legal_basis", "order", "is_active"]


class DisclosureForm(BaseModelForm):
    version_note = forms.CharField(label="Ghi chú cập nhật (lưu vào lịch sử)", max_length=255, required=False)

    class Meta:
        model = Disclosure
        fields = ["title", "section", "school_year", "description", "file", "disclosure_date", "valid_until",
                  "review_due", "responsible"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].queryset = DisclosureSection.objects.filter(is_active=True)


class AuthorityCheckForm(BaseForm):
    confirmed = forms.BooleanField(
        label="Tôi xác nhận đã kiểm tra nội dung công khai này theo thẩm quyền", required=False)
    note = forms.CharField(label="Ghi chú kiểm tra", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}))

