"""Nghiệp vụ nội bộ: văn bản, kế hoạch giáo dục, nhiệm vụ, minh chứng."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.permissions import (
    MANAGER_ROLES, ROLE_ADMIN, ROLE_GROUP_LEADER, ROLE_OFFICE, ROLE_PRINCIPAL, has_full_scope,
)
from apps.core.storage import UniqueUploadPath, get_protected_storage
from apps.core.validators import validate_document_upload
from apps.core.workflow import TimeStampedByModel

ACCESS_LEVELS = [
    ("all", "Toàn bộ cán bộ, giáo viên, nhân viên"),
    ("managers", "Lãnh đạo và văn phòng"),
    ("restricted", "Chỉ người được chỉ định"),
]


# ---------------------------------------------------------------------------
# Văn bản
# ---------------------------------------------------------------------------
class OfficialDocumentQuerySet(models.QuerySet):
    def for_user(self, user):
        if user.is_superuser or user.role in {ROLE_ADMIN, ROLE_PRINCIPAL}:
            return self
        own = Q(created_by=user) | Q(responsible=user) | Q(allowed_users=user)
        if user.role in MANAGER_ROLES | {ROLE_OFFICE}:
            return self.filter(Q(access_level__in=["all", "managers"]) | own).distinct()
        return self.filter(Q(access_level="all") | own).distinct()


class OfficialDocument(TimeStampedByModel):
    DIRECTIONS = [("in", "Văn bản đến"), ("out", "Văn bản đi"), ("internal", "Văn bản nội bộ")]
    STATUSES = [("new", "Mới"), ("processing", "Đang xử lý"), ("done", "Đã xử lý"), ("archived", "Lưu trữ")]

    direction = models.CharField("Loại sổ", max_length=10, choices=DIRECTIONS, default="in", db_index=True)
    number = models.CharField("Số", max_length=30, db_index=True)
    symbol = models.CharField("Ký hiệu", max_length=60, blank=True, db_index=True)
    issue_date = models.DateField("Ngày ban hành", db_index=True)
    issuer = models.ForeignKey("org.Catalog", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                               limit_choices_to={"kind": "issuer"}, verbose_name="Cơ quan ban hành")
    issuer_text = models.CharField("Cơ quan ban hành (nếu chưa có trong danh mục)", max_length=200, blank=True)
    doc_type = models.ForeignKey("org.Catalog", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                 limit_choices_to={"kind": "doc_type"}, verbose_name="Loại văn bản")
    field = models.ForeignKey("org.Catalog", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                              limit_choices_to={"kind": "field"}, verbose_name="Lĩnh vực")
    summary = models.CharField("Trích yếu", max_length=500)
    content_text = models.TextField("Nội dung chính (phục vụ tìm kiếm)", blank=True)
    file = models.FileField("Tệp đính kèm", upload_to=UniqueUploadPath("official_docs"), storage=get_protected_storage,
                            blank=True, validators=[validate_document_upload])
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+", verbose_name="Người phụ trách")
    processing_status = models.CharField("Trạng thái xử lý", max_length=20, choices=STATUSES, default="new", db_index=True)
    deadline = models.DateField("Hạn xử lý", null=True, blank=True)
    access_level = models.CharField("Phạm vi truy cập", max_length=20, choices=ACCESS_LEVELS, default="all")
    allowed_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="+",
                                           verbose_name="Người được xem (khi chỉ định)")

    objects = OfficialDocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        verbose_name = "Văn bản"
        verbose_name_plural = "Văn bản"
        indexes = [models.Index(fields=["direction", "-issue_date"])]

    def __str__(self):
        sym = f"/{self.symbol}" if self.symbol else ""
        return f"{self.number}{sym} - {self.summary[:80]}"

    @property
    def issuer_name(self):
        return str(self.issuer) if self.issuer else self.issuer_text

    @property
    def is_overdue(self):
        return bool(self.deadline and self.deadline < timezone.localdate() and self.processing_status in ("new", "processing"))


# ---------------------------------------------------------------------------
# Kế hoạch giáo dục
# ---------------------------------------------------------------------------
class PlanExportTemplate(models.Model):
    """Mẫu xuất kế hoạch (Word/PDF): phần đầu, phần chữ ký... cấu hình được."""

    name = models.CharField("Tên mẫu", max_length=150, unique=True)
    header_left = models.TextField("Phần đầu bên trái", blank=True,
                                   help_text="Ví dụ: tên cơ quan chủ quản, tên trường. Mỗi dòng một dòng.")
    header_right = models.TextField("Phần đầu bên phải", blank=True,
                                    default="CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc")
    title_prefix = models.CharField("Tiền tố tiêu đề", max_length=100, blank=True, default="KẾ HOẠCH")
    signature_title = models.CharField("Chức danh ký", max_length=150, blank=True, default="HIỆU TRƯỞNG")
    footer_note = models.TextField("Nơi nhận / ghi chú cuối", blank=True)
    is_default = models.BooleanField("Mẫu mặc định", default=False)

    class Meta:
        verbose_name = "Mẫu xuất kế hoạch"
        verbose_name_plural = "Mẫu xuất kế hoạch"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            PlanExportTemplate.objects.exclude(pk=self.pk).update(is_default=False)


class EducationPlanQuerySet(models.QuerySet):
    def for_user(self, user):
        if has_full_scope(user):
            return self
        cond = Q(created_by=user)
        cond |= Q(level="school", status__in=["approved", "official"])
        if user.group_id:
            if user.role == ROLE_GROUP_LEADER:
                cond |= Q(group_id=user.group_id)
            else:
                cond |= Q(group_id=user.group_id, status__in=["consulting", "approved", "official"])
        class_ids = list(user.classes.values_list("pk", flat=True))
        if class_ids:
            cond |= Q(school_class_id__in=class_ids)
        return self.filter(cond).distinct()


class EducationPlan(TimeStampedByModel):
    LEVELS = [
        ("school", "Kế hoạch giáo dục nhà trường"),
        ("group", "Kế hoạch giáo dục tổ chuyên môn"),
        ("class", "Kế hoạch giáo dục lớp"),
        ("theme", "Kế hoạch chủ đề"),
        ("week", "Kế hoạch tuần"),
        ("activity", "Kế hoạch hoạt động"),
    ]
    STATUSES = [
        ("draft", "Dự thảo"),
        ("consulting", "Đang lấy góp ý"),
        ("pending", "Chờ duyệt"),
        ("approved", "Đã duyệt"),
        ("official", "Chính thức (ban hành)"),
        ("archived", "Lưu trữ"),
    ]
    BADGES = {"draft": "secondary", "consulting": "info", "pending": "warning", "approved": "primary",
              "official": "success", "archived": "light"}

    title = models.CharField("Tên kế hoạch", max_length=255)
    level = models.CharField("Cấp kế hoạch", max_length=10, choices=LEVELS, db_index=True)
    school_year = models.ForeignKey("org.SchoolYear", on_delete=models.PROTECT, verbose_name="Năm học", related_name="plans")
    group = models.ForeignKey("org.ProfessionalGroup", on_delete=models.SET_NULL, null=True, blank=True,
                              verbose_name="Tổ chuyên môn", related_name="plans")
    school_class = models.ForeignKey("org.SchoolClass", on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name="Lớp", related_name="plans")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children",
                               verbose_name="Thuộc kế hoạch")
    period_start = models.DateField("Từ ngày", null=True, blank=True)
    period_end = models.DateField("Đến ngày", null=True, blank=True)
    content = models.TextField("Nội dung kế hoạch", blank=True)
    file = models.FileField("Tệp kế hoạch", upload_to=UniqueUploadPath("plans"), storage=get_protected_storage,
                            blank=True, validators=[validate_document_upload])
    status = models.CharField("Trạng thái", max_length=20, choices=STATUSES, default="draft", db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+", editable=False, verbose_name="Người duyệt")
    approved_at = models.DateTimeField("Thời điểm duyệt", null=True, blank=True, editable=False)
    official_at = models.DateTimeField("Thời điểm ban hành", null=True, blank=True, editable=False)

    objects = EducationPlanQuerySet.as_manager()

    class Meta:
        ordering = ["-school_year__start_date", "level", "-created_at"]
        verbose_name = "Kế hoạch giáo dục"
        verbose_name_plural = "Kế hoạch giáo dục"

    def __str__(self):
        return self.title

    @property
    def status_badge(self):
        return self.BADGES.get(self.status, "secondary")

    @property
    def is_editable(self):
        return self.status in ("draft", "consulting")

    @property
    def latest_version(self):
        return self.versions.order_by("-version_no").first()


class PlanVersion(models.Model):
    plan = models.ForeignKey(EducationPlan, on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveIntegerField("Phiên bản")
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to=UniqueUploadPath("plans/history"), storage=get_protected_storage, blank=True)
    status = models.CharField(max_length=20)
    note = models.CharField("Ghi chú", max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-version_no"]
        constraints = [models.UniqueConstraint(fields=["plan", "version_no"], name="uniq_plan_version")]


class PlanComment(models.Model):
    plan = models.ForeignKey(EducationPlan, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    content = models.TextField("Góp ý", max_length=3000)
    version_no = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]


# ---------------------------------------------------------------------------
# Nhiệm vụ
# ---------------------------------------------------------------------------
class TaskQuerySet(models.QuerySet):
    def for_user(self, user):
        if has_full_scope(user):
            return self
        cond = Q(assignee=user) | Q(created_by=user)
        if user.group_id:
            cond |= Q(assigned_group_id=user.group_id, assignee__isnull=True)
            if user.role == ROLE_GROUP_LEADER:
                cond |= Q(assigned_group_id=user.group_id)
        if user.campus_id:
            cond |= Q(assigned_campus_id=user.campus_id, assignee__isnull=True, assigned_group__isnull=True)
        return self.filter(cond).distinct()

    def overdue(self):
        return self.filter(due_date__lt=timezone.localdate()).exclude(status="done")

    def open(self):
        return self.exclude(status="done")


class Task(TimeStampedByModel):
    STATUSES = [
        ("todo", "Chưa thực hiện"),
        ("in_progress", "Đang thực hiện"),
        ("waiting", "Chờ xác nhận"),
        ("done", "Hoàn thành"),
    ]
    BADGES = {"todo": "secondary", "in_progress": "primary", "waiting": "warning", "done": "success", "overdue": "danger"}
    PRIORITIES = [("low", "Thấp"), ("normal", "Bình thường"), ("high", "Cao")]

    title = models.CharField("Tên nhiệm vụ", max_length=255)
    description = models.TextField("Mô tả công việc", blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="assigned_tasks", verbose_name="Người phụ trách")
    assigned_group = models.ForeignKey("org.ProfessionalGroup", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="tasks", verbose_name="Giao cho tổ")
    assigned_campus = models.ForeignKey("org.Campus", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="tasks", verbose_name="Giao cho điểm trường")
    due_date = models.DateField("Thời hạn", null=True, blank=True, db_index=True)
    priority = models.CharField("Mức ưu tiên", max_length=10, choices=PRIORITIES, default="normal")
    status = models.CharField("Trạng thái", max_length=20, choices=STATUSES, default="todo", db_index=True)
    plan = models.ForeignKey(EducationPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks",
                             verbose_name="Thuộc kế hoạch")
    completed_at = models.DateTimeField("Hoàn thành lúc", null=True, blank=True, editable=False)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="+", editable=False, verbose_name="Người xác nhận")

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["status", "due_date", "-created_at"]
        verbose_name = "Nhiệm vụ"
        verbose_name_plural = "Nhiệm vụ"

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status != "done")

    @property
    def display_status(self):
        return "Quá hạn" if self.is_overdue else self.get_status_display()

    @property
    def status_badge(self):
        return self.BADGES["overdue" if self.is_overdue else self.status]

    @property
    def group(self):
        """Dùng cho kiểm tra quyền tổ trưởng (owns_or_scoped)."""
        return self.assigned_group

    @property
    def group_id(self):
        return self.assigned_group_id

    @property
    def target_label(self):
        parts = [str(x) for x in (self.assignee, self.assigned_group, self.assigned_campus) if x]
        return ", ".join(parts) or "—"


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    content = models.TextField("Nội dung", max_length=3000)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField("Minh chứng", upload_to=UniqueUploadPath("tasks"), storage=get_protected_storage,
                            validators=[validate_document_upload])
    original_name = models.CharField(max_length=255, blank=True)
    description = models.CharField("Mô tả", max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-uploaded_at"]


# ---------------------------------------------------------------------------
# Minh chứng
# ---------------------------------------------------------------------------
class EvidenceCategory(models.Model):
    code = models.CharField("Mã", max_length=30, unique=True)
    name = models.CharField("Tên danh mục / tiêu chí", max_length=255)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children",
                               verbose_name="Danh mục cha")
    description = models.TextField("Mô tả", blank=True)
    order = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = "Danh mục minh chứng"
        verbose_name_plural = "Danh mục minh chứng"

    def __str__(self):
        return f"{self.code} - {self.name}"


class EvidenceQuerySet(models.QuerySet):
    def for_user(self, user):
        if has_full_scope(user):
            return self
        cond = Q(created_by=user) | Q(responsible=user)
        base = Q(access_level="all") & (Q(group__isnull=True) | Q(group_id=user.group_id))
        if user.campus_id:
            base &= Q(campus__isnull=True) | Q(campus_id=user.campus_id)
        else:
            base &= Q(campus__isnull=True)
        return self.filter(cond | base).distinct()


class Evidence(TimeStampedByModel):
    code = models.CharField("Mã minh chứng", max_length=50, unique=True)
    title = models.CharField("Tên minh chứng", max_length=255)
    category = models.ForeignKey(EvidenceCategory, on_delete=models.PROTECT, related_name="evidences",
                                 verbose_name="Danh mục / tiêu chí")
    description = models.TextField("Mô tả", blank=True)
    source = models.CharField("Nguồn / nơi ban hành", max_length=255, blank=True)
    evidence_date = models.DateField("Ngày tạo minh chứng", null=True, blank=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+", verbose_name="Người phụ trách")
    school_year = models.ForeignKey("org.SchoolYear", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                    verbose_name="Năm học")
    campus = models.ForeignKey("org.Campus", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                               verbose_name="Điểm trường")
    group = models.ForeignKey("org.ProfessionalGroup", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="+", verbose_name="Tổ chuyên môn")
    plan = models.ForeignKey(EducationPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidences",
                             verbose_name="Gắn với kế hoạch")
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidences",
                             verbose_name="Gắn với nhiệm vụ")
    criterion = models.CharField("Tiêu chí / chỉ báo", max_length=255, blank=True)
    report_ref = models.CharField("Báo cáo liên quan", max_length=255, blank=True)
    access_level = models.CharField("Phạm vi truy cập", max_length=20,
                                    choices=[c for c in ACCESS_LEVELS if c[0] != "restricted"], default="all")

    objects = EvidenceQuerySet.as_manager()

    class Meta:
        ordering = ["category__order", "code"]
        verbose_name = "Minh chứng"
        verbose_name_plural = "Minh chứng"

    def __str__(self):
        return f"{self.code} - {self.title}"

    @property
    def current_file(self):
        return self.files.order_by("-version_no").first()


class EvidenceFile(models.Model):
    """Mỗi lần tải lên tạo một phiên bản mới; không ghi đè tệp cũ."""

    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name="files")
    version_no = models.PositiveIntegerField("Phiên bản")
    file = models.FileField("Tệp", upload_to=UniqueUploadPath("evidence"), storage=get_protected_storage,
                            validators=[validate_document_upload])
    original_name = models.CharField(max_length=255, blank=True)
    note = models.CharField("Ghi chú", max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-version_no"]
        constraints = [models.UniqueConstraint(fields=["evidence", "version_no"], name="uniq_evidence_version")]
