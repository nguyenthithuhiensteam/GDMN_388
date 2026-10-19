from django import forms

from apps.accounts.models import User
from apps.accounts.permissions import ROLE_GROUP_LEADER, has_full_scope, is_manager
from apps.core.forms_base import BaseForm, BaseModelForm
from apps.core.validators import validate_document_upload
from apps.org.models import Catalog, SchoolClass

from .models import (
    EducationPlan, Evidence, EvidenceCategory, OfficialDocument, PlanExportTemplate, Task,
)


class OfficialDocumentForm(BaseModelForm):
    class Meta:
        model = OfficialDocument
        fields = ["direction", "number", "symbol", "issue_date", "issuer", "issuer_text", "doc_type", "field",
                  "summary", "content_text", "file", "responsible", "processing_status", "deadline",
                  "access_level", "allowed_users"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 2}), "content_text": forms.Textarea(attrs={"rows": 5}),
                   "allowed_users": forms.SelectMultiple(attrs={"size": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = User.objects.filter(is_active=True)
        self.fields["responsible"].queryset = active
        self.fields["allowed_users"].queryset = active
        for name, kind in (("issuer", "issuer"), ("doc_type", "doc_type"), ("field", "field")):
            self.fields[name].queryset = Catalog.objects.filter(kind=kind, is_active=True)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("issuer") and not cleaned.get("issuer_text"):
            self.add_error("issuer", "Chọn cơ quan ban hành hoặc nhập tên cơ quan.")
        return cleaned


class EducationPlanForm(BaseModelForm):
    version_note = forms.CharField(label="Ghi chú phiên bản", max_length=255, required=False)

    class Meta:
        model = EducationPlan
        fields = ["title", "level", "school_year", "group", "school_class", "parent", "period_start", "period_end",
                  "content", "file"]
        widgets = {"content": forms.Textarea(attrs={"rows": 14})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.user
        self.fields["parent"].queryset = EducationPlan.objects.for_user(user).exclude(pk=self.instance.pk)
        if not has_full_scope(user):
            # Giáo viên/tổ trưởng chỉ lập kế hoạch cho tổ/lớp của mình, không lập KH cấp trường.
            self.fields["level"].choices = [c for c in EducationPlan.LEVELS if c[0] != "school"]
            self.fields["group"].queryset = self.fields["group"].queryset.filter(pk=user.group_id)
            if user.role == ROLE_GROUP_LEADER and user.group_id:
                self.fields["school_class"].queryset = SchoolClass.objects.filter(group_id=user.group_id)
            else:
                self.fields["school_class"].queryset = user.classes.all()

    def clean(self):
        cleaned = super().clean()
        level = cleaned.get("level")
        if level == "group" and not cleaned.get("group"):
            self.add_error("group", "Kế hoạch tổ chuyên môn cần chọn tổ.")
        if level in ("class", "theme", "week", "activity") and not cleaned.get("school_class") and not cleaned.get("group"):
            self.add_error("school_class", "Chọn lớp (hoặc tổ) áp dụng kế hoạch.")
        s, e = cleaned.get("period_start"), cleaned.get("period_end")
        if s and e and e < s:
            self.add_error("period_end", "Ngày kết thúc phải sau ngày bắt đầu.")
        if not cleaned.get("content") and not cleaned.get("file") and not self.instance.file:
            raise forms.ValidationError("Cần nhập nội dung hoặc đính kèm tệp kế hoạch.")
        return cleaned


class PlanCommentForm(BaseForm):
    content = forms.CharField(label="Góp ý", max_length=3000, widget=forms.Textarea(attrs={"rows": 3}))


class PlanExportTemplateForm(BaseModelForm):
    class Meta:
        model = PlanExportTemplate
        fields = ["name", "header_left", "header_right", "title_prefix", "signature_title", "footer_note", "is_default"]


class TaskForm(BaseModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "assignee", "assigned_group", "assigned_campus", "due_date", "priority", "plan"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.user
        active = User.objects.filter(is_active=True)
        self.fields["plan"].queryset = EducationPlan.objects.for_user(user)
        if is_manager(user) or has_full_scope(user):
            self.fields["assignee"].queryset = active
        else:
            # Tổ trưởng chỉ giao việc trong tổ của mình
            self.fields["assignee"].queryset = active.filter(group_id=user.group_id) if user.group_id else active.none()
            self.fields["assigned_group"].queryset = self.fields["assigned_group"].queryset.filter(pk=user.group_id)
            self.fields["assigned_campus"].queryset = self.fields["assigned_campus"].queryset.none()

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) for f in ("assignee", "assigned_group", "assigned_campus")):
            raise forms.ValidationError("Cần chọn người phụ trách, tổ hoặc điểm trường được giao.")
        return cleaned


class TaskStatusForm(BaseForm):
    status = forms.ChoiceField(label="Cập nhật trạng thái", choices=[])
    note = forms.CharField(label="Ghi chú", max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = choices


class CommentForm(BaseForm):
    content = forms.CharField(label="Nhận xét / phản hồi", max_length=3000, widget=forms.Textarea(attrs={"rows": 3}))


class AttachmentForm(BaseForm):
    file = forms.FileField(label="Tệp minh chứng", validators=[validate_document_upload])
    description = forms.CharField(label="Mô tả", max_length=255, required=False)


class EvidenceCategoryForm(BaseModelForm):
    class Meta:
        model = EvidenceCategory
        fields = ["code", "name", "parent", "description", "order"]


class EvidenceForm(BaseModelForm):
    upload = forms.FileField(label="Tệp minh chứng", required=False, validators=[validate_document_upload])
    upload_note = forms.CharField(label="Ghi chú tệp", max_length=255, required=False)

    class Meta:
        model = Evidence
        fields = ["code", "title", "category", "description", "source", "evidence_date", "responsible", "school_year",
                  "campus", "group", "plan", "task", "criterion", "report_ref", "access_level"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.user
        self.fields["responsible"].queryset = User.objects.filter(is_active=True)
        self.fields["plan"].queryset = EducationPlan.objects.for_user(user)
        self.fields["task"].queryset = Task.objects.for_user(user)
        if not has_full_scope(user):
            self.fields["group"].queryset = self.fields["group"].queryset.filter(pk=user.group_id)
            self.fields["campus"].queryset = self.fields["campus"].queryset.filter(pk=user.campus_id)


class EvidenceFileForm(BaseForm):
    file = forms.FileField(label="Tệp (tạo phiên bản mới)", validators=[validate_document_upload])
    note = forms.CharField(label="Ghi chú", max_length=255, required=False)
