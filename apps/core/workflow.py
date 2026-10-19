"""
Quy trình duyệt nội dung dùng chung: Nháp → Chờ duyệt → Đã duyệt → Đã xuất bản → Ẩn / Lưu trữ.

Mỗi chuyển trạng thái yêu cầu một quyền trong ma trận phân quyền và được ghi nhật ký.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.permissions import has_perm


class Status(models.TextChoices):
    DRAFT = "draft", "Nháp"
    PENDING = "pending", "Chờ duyệt"
    APPROVED = "approved", "Đã duyệt"
    PUBLISHED = "published", "Đã xuất bản"
    HIDDEN = "hidden", "Đã ẩn"
    ARCHIVED = "archived", "Lưu trữ"


STATUS_BADGES = {
    "draft": "secondary", "pending": "warning", "approved": "info",
    "published": "success", "hidden": "dark", "archived": "light",
}


class TimeStampedByModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="+", verbose_name="Người tạo",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="+", verbose_name="Người sửa",
    )
    created_at = models.DateTimeField("Ngày tạo", default=timezone.now, editable=False)
    updated_at = models.DateTimeField("Cập nhật", auto_now=True)

    class Meta:
        abstract = True


class WorkflowModel(TimeStampedByModel):
    status = models.CharField("Trạng thái", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="+", verbose_name="Người duyệt",
    )
    approved_at = models.DateTimeField("Thời điểm duyệt", null=True, blank=True, editable=False)
    published_at = models.DateTimeField("Thời điểm xuất bản", null=True, blank=True, editable=False)
    review_note = models.CharField("Ghi chú duyệt", max_length=500, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def status_badge(self):
        return STATUS_BADGES.get(self.status, "secondary")

    @property
    def is_public(self):
        return self.status == Status.PUBLISHED


# tên: (nhãn, trạng thái nguồn, trạng thái đích, thao tác cần quyền, kiểu nút)
TRANSITIONS = {
    "submit": ("Gửi duyệt", {Status.DRAFT}, Status.PENDING, "edit", "primary"),
    "approve": ("Phê duyệt", {Status.PENDING}, Status.APPROVED, "approve", "success"),
    "reject": ("Trả lại", {Status.PENDING, Status.APPROVED}, Status.DRAFT, "approve", "warning"),
    "publish": ("Xuất bản", {Status.APPROVED, Status.HIDDEN}, Status.PUBLISHED, "publish", "success"),
    "hide": ("Ẩn", {Status.PUBLISHED}, Status.HIDDEN, "publish", "secondary"),
    "archive": ("Lưu trữ", {Status.PUBLISHED, Status.HIDDEN, Status.APPROVED, Status.DRAFT}, Status.ARCHIVED, "publish", "secondary"),
    "restore": ("Khôi phục về nháp", {Status.HIDDEN, Status.ARCHIVED}, Status.DRAFT, "publish", "outline-secondary"),
}


def _sources(name, require_approval):
    label, sources, target, perm, style = TRANSITIONS[name]
    if name == "publish" and not require_approval:
        sources = sources | {Status.DRAFT, Status.PENDING}
    return sources


def can_transition(user, obj, module, name):
    from .models import SiteSettings
    from .permissions_mixins import owns_or_scoped

    if name not in TRANSITIONS:
        return False
    _, _, _, perm, _ = TRANSITIONS[name]
    require_approval = SiteSettings.load().require_approval
    if obj.status not in _sources(name, require_approval):
        return False
    if not has_perm(user, module, perm):
        return False
    if perm == "edit" and not owns_or_scoped(user, obj):
        return False
    return True


def available_transitions(user, obj, module):
    result = []
    for name, (label, _, _, _, style) in TRANSITIONS.items():
        if can_transition(user, obj, module, name):
            result.append({"name": name, "label": label, "style": style})
    return result


def apply_transition(request, obj, module, name, note=""):
    """Thực hiện chuyển trạng thái (đã kiểm tra quyền trước đó bằng can_transition)."""
    from .audit import log_action

    _, _, target, _, _ = TRANSITIONS[name]
    old = obj.status
    obj.status = target
    obj.updated_by = request.user
    now = timezone.now()
    if name == "approve":
        obj.approved_by = request.user
        obj.approved_at = now
    if name == "publish":
        if not obj.approved_by_id:
            obj.approved_by = request.user
            obj.approved_at = now
        obj.published_at = obj.published_at or now
    if name == "reject":
        obj.approved_by = None
        obj.approved_at = None
    if note:
        obj.review_note = note[:500]
    obj.save()
    log_action(request, f"workflow:{name}", obj, module=module, changes={"status": [old, target], "note": note})
    return obj
