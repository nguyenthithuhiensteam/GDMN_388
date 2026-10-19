"""Nội dung website công khai: tin tức, thông báo, trang giới thiệu, album, tài liệu, công khai giáo dục."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.sanitize import clean_html
from apps.core.storage import UniqueUploadPath, get_protected_storage
from apps.core.validators import validate_document_upload, validate_image_upload
from apps.core.workflow import Status, TimeStampedByModel, WorkflowModel


def unique_slug(instance, value, field="slug", max_length=200):
    base = slugify(value)[: max_length - 10] or "noi-dung"
    slug, i = base, 2
    model = type(instance)
    while model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


class SluggedMixin(models.Model):
    slug = models.SlugField("Đường dẫn", max_length=200, unique=True, blank=True, allow_unicode=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, getattr(self, "title", "") or getattr(self, "name", ""))
        super().save(*args, **kwargs)


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Status.PUBLISHED)


class Category(SluggedMixin):
    name = models.CharField("Tên danh mục", max_length=150, unique=True)
    description = models.CharField("Mô tả", max_length=255, blank=True)
    order = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Danh mục tin"
        verbose_name_plural = "Danh mục tin"

    def __str__(self):
        return self.name


class Post(SluggedMixin, WorkflowModel):
    title = models.CharField("Tiêu đề", max_length=255)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="Danh mục", related_name="posts")
    summary = models.TextField("Tóm tắt", max_length=500, blank=True)
    body = models.TextField("Nội dung", help_text="Cho phép định dạng cơ bản; mã HTML nguy hiểm sẽ bị loại bỏ.")
    thumbnail = models.ImageField("Ảnh đại diện", upload_to=UniqueUploadPath("posts"), blank=True, validators=[validate_image_upload])
    thumbnail_consent = models.BooleanField(
        "Ảnh đại diện không có trẻ em hoặc đã có sự đồng ý của cha mẹ trẻ",
        default=False,
        help_text="Bắt buộc xác nhận nếu có ảnh đại diện trước khi xuất bản.",
    )
    is_featured = models.BooleanField("Hoạt động nổi bật", default=False)
    group = models.ForeignKey(
        "org.ProfessionalGroup", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tổ chuyên môn", related_name="+"
    )
    view_count = models.PositiveIntegerField("Lượt xem", default=0, editable=False)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Tin bài"
        verbose_name_plural = "Tin tức"
        indexes = [models.Index(fields=["status", "-published_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("public:post_detail", kwargs={"slug": self.slug})

    def publish_blockers(self):
        if self.thumbnail and not self.thumbnail_consent:
            return ["Chưa xác nhận quyền sử dụng ảnh đại diện."]
        return []

    @property
    def author_name(self):
        return self.created_by.get_full_name() if self.created_by else ""


class Announcement(SluggedMixin, WorkflowModel):
    KINDS = [
        ("school", "Thông báo nhà trường"),
        ("admission", "Thông báo tuyển sinh"),
        ("schedule", "Lịch hoạt động"),
        ("urgent", "Thông báo khẩn"),
    ]
    title = models.CharField("Tiêu đề", max_length=255)
    kind = models.CharField("Loại thông báo", max_length=20, choices=KINDS, default="school", db_index=True)
    body = models.TextField("Nội dung")
    attachment = models.FileField(
        "Tệp đính kèm",
        upload_to=UniqueUploadPath("announcements"),
        blank=True,
        storage=get_protected_storage,
        validators=[validate_document_upload],
    )
    event_date = models.DateTimeField("Thời gian diễn ra (nếu là lịch hoạt động)", null=True, blank=True)
    start_date = models.DateField("Hiển thị từ ngày", default=timezone.localdate)
    end_date = models.DateField("Hết hạn hiển thị", null=True, blank=True, help_text="Để trống nếu không có thời hạn.")
    is_pinned = models.BooleanField("Ghim lên đầu", default=False)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["-is_pinned", "-start_date", "-created_at"]
        verbose_name = "Thông báo"
        verbose_name_plural = "Thông báo"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("public:announcement_detail", kwargs={"slug": self.slug})

    @classmethod
    def visible(cls):
        today = timezone.localdate()
        return cls.objects.published().filter(start_date__lte=today).filter(Q(end_date__isnull=True) | Q(end_date__gte=today))

    @property
    def is_active_now(self):
        today = timezone.localdate()
        return self.status == Status.PUBLISHED and self.start_date <= today and (self.end_date is None or self.end_date >= today)


class Page(SluggedMixin, WorkflowModel):
    SECTIONS = [
        ("lich-su", "Lịch sử hình thành và phát triển"),
        ("su-menh", "Sứ mệnh, tầm nhìn, giá trị cốt lõi"),
        ("co-cau", "Cơ cấu tổ chức"),
        ("co-so-vat-chat", "Cơ sở vật chất và các điểm trường"),
        ("chuong-trinh", "Chương trình giáo dục"),
        ("tuyen-sinh", "Tuyển sinh"),
        ("khac", "Trang khác"),
    ]
    title = models.CharField("Tiêu đề", max_length=255)
    section = models.CharField("Mục", max_length=30, choices=SECTIONS, default="khac")
    body = models.TextField("Nội dung")
    image = models.ImageField("Ảnh minh họa", upload_to=UniqueUploadPath("pages"), blank=True, validators=[validate_image_upload])
    order = models.PositiveIntegerField("Thứ tự", default=0)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Trang giới thiệu"
        verbose_name_plural = "Trang giới thiệu"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("public:page_detail", kwargs={"slug": self.slug})


class StaffProfile(TimeStampedByModel):
    """Hồ sơ hiển thị công khai của đội ngũ (tách biệt với tài khoản đăng nhập)."""

    GROUPS = [("bgh", "Ban giám hiệu"), ("gv", "Giáo viên"), ("nv", "Nhân viên")]
    full_name = models.CharField("Họ và tên", max_length=150)
    position = models.CharField("Chức vụ", max_length=150)
    staff_group = models.CharField("Nhóm", max_length=10, choices=GROUPS, default="gv")
    photo = models.ImageField("Ảnh", upload_to=UniqueUploadPath("staff"), blank=True, validators=[validate_image_upload])
    bio = models.TextField("Giới thiệu ngắn", blank=True, max_length=1000)
    order = models.PositiveIntegerField("Thứ tự", default=0)
    public_consent = models.BooleanField("Người này đồng ý công khai thông tin/ảnh", default=False)
    is_visible = models.BooleanField("Hiển thị trên website", default=True)

    class Meta:
        ordering = ["staff_group", "order", "full_name"]
        verbose_name = "Đội ngũ"
        verbose_name_plural = "Đội ngũ"

    def __str__(self):
        return f"{self.full_name} - {self.position}"


class Album(SluggedMixin, WorkflowModel):
    KINDS = [("event", "Sự kiện"), ("class", "Lớp"), ("topic", "Chủ đề"), ("other", "Khác")]
    VISIBILITY = [("public", "Công khai"), ("internal", "Nội bộ")]
    title = models.CharField("Tên album", max_length=255)
    kind = models.CharField("Loại album", max_length=10, choices=KINDS, default="event")
    school_year = models.ForeignKey(
        "org.SchoolYear", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Năm học", related_name="+"
    )
    campus = models.ForeignKey("org.Campus", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Điểm trường", related_name="+")
    school_class = models.ForeignKey(
        "org.SchoolClass", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Lớp", related_name="+"
    )
    group = models.ForeignKey(
        "org.ProfessionalGroup", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tổ chuyên môn", related_name="+"
    )
    event_date = models.DateField("Ngày sự kiện", null=True, blank=True)
    description = models.TextField("Mô tả", blank=True)
    visibility = models.CharField("Phạm vi", max_length=10, choices=VISIBILITY, default="public")

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["-event_date", "-created_at"]
        verbose_name = "Album"
        verbose_name_plural = "Thư viện ảnh/video"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("public:album_detail", kwargs={"slug": self.slug})

    def public_items(self):
        return self.items.filter(consent_status=MediaItem.CONSENT_APPROVED)

    @property
    def cover(self):
        return self.public_items().filter(media_type="image").first()

    @property
    def pending_consent_count(self):
        return self.items.filter(consent_status=MediaItem.CONSENT_PENDING).count()


class MediaItem(models.Model):
    """Ảnh hoặc video trong album. Tệp ảnh nằm trong kho nội bộ và chỉ phục vụ công khai
    khi album đã xuất bản, ở phạm vi công khai, và ảnh đã được xác nhận quyền sử dụng."""

    CONSENT_PENDING = "pending"
    CONSENT_APPROVED = "approved"
    CONSENT_REJECTED = "rejected"
    CONSENT_CHOICES = [
        (CONSENT_PENDING, "Chưa kiểm tra quyền sử dụng hình ảnh"),
        (CONSENT_APPROVED, "Đã xác nhận được phép công khai"),
        (CONSENT_REJECTED, "Không được công khai"),
    ]
    TYPES = [("image", "Ảnh"), ("video", "Video (liên kết)")]
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="items", verbose_name="Album")
    media_type = models.CharField("Loại", max_length=10, choices=TYPES, default="image")
    image = models.ImageField(
        "Ảnh", upload_to=UniqueUploadPath("album"), storage=get_protected_storage, blank=True, validators=[validate_image_upload]
    )
    video_url = models.URLField("Liên kết video (YouTube)", blank=True)
    caption = models.CharField("Chú thích", max_length=255, blank=True)
    has_children = models.BooleanField("Có hình ảnh trẻ em", default=True)
    consent_status = models.CharField(
        "Quyền sử dụng hình ảnh", max_length=10, choices=CONSENT_CHOICES, default=CONSENT_PENDING, db_index=True
    )
    consent_note = models.CharField(
        "Căn cứ xác nhận", max_length=255, blank=True, help_text="Ví dụ: phiếu đồng ý của cha mẹ trẻ lưu tại văn phòng, số ..."
    )
    consent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Người xác nhận"
    )
    consent_at = models.DateTimeField("Thời điểm xác nhận", null=True, blank=True)
    order = models.PositiveIntegerField("Thứ tự", default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+", verbose_name="Người tải lên"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order", "uploaded_at"]
        verbose_name = "Ảnh/video"
        verbose_name_plural = "Ảnh/video"

    def __str__(self):
        return self.caption or f"#{self.pk}"

    @property
    def youtube_id(self):
        import re

        m = re.search(r"(?:youtu\.be/|v=|embed/)([A-Za-z0-9_-]{11})", self.video_url or "")
        return m.group(1) if m else ""

    def is_publicly_visible(self):
        a = self.album
        return a.status == Status.PUBLISHED and a.visibility == "public" and self.consent_status == self.CONSENT_APPROVED


class PublicDocument(WorkflowModel):
    CATEGORIES = [
        ("bieu-mau", "Biểu mẫu"),
        ("huong-dan", "Hướng dẫn cho cha mẹ trẻ"),
        ("van-ban", "Văn bản công bố"),
        ("khac", "Tài liệu khác"),
    ]
    title = models.CharField("Tên tài liệu", max_length=255)
    category = models.CharField("Danh mục", max_length=20, choices=CATEGORIES, default="khac")
    description = models.TextField("Mô tả", blank=True)
    file = models.FileField(
        "Tệp", upload_to=UniqueUploadPath("public_docs"), storage=get_protected_storage, validators=[validate_document_upload]
    )
    download_count = models.PositiveIntegerField("Lượt tải", default=0, editable=False)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Tài liệu tải xuống"
        verbose_name_plural = "Tài liệu tải xuống"

    def __str__(self):
        return self.title


class DisclosureSection(models.Model):
    """Mục công khai giáo dục, cấu hình được để cập nhật theo quy định hiện hành."""

    name = models.CharField("Tên mục", max_length=255, unique=True)
    legal_basis = models.CharField(
        "Căn cứ (do nhà trường ghi)",
        max_length=255,
        blank=True,
        help_text="Ghi căn cứ văn bản quy phạm hiện hành sau khi đã được kiểm tra.",
    )
    order = models.PositiveIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Mục công khai"
        verbose_name_plural = "Mục công khai"

    def __str__(self):
        return self.name


class Disclosure(WorkflowModel):
    title = models.CharField("Tiêu đề", max_length=255)
    section = models.ForeignKey(DisclosureSection, on_delete=models.PROTECT, verbose_name="Mục công khai", related_name="items")
    school_year = models.ForeignKey(
        "org.SchoolYear", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Năm học", related_name="+"
    )
    description = models.TextField("Nội dung tóm tắt", blank=True)
    file = models.FileField(
        "Tệp công khai",
        upload_to=UniqueUploadPath("disclosures"),
        storage=get_protected_storage,
        blank=True,
        validators=[validate_document_upload],
    )
    disclosure_date = models.DateField("Ngày công bố", null=True, blank=True)
    valid_until = models.DateField("Thời hạn công khai đến", null=True, blank=True)
    review_due = models.DateField("Hạn rà soát tiếp theo", null=True, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Người phụ trách"
    )
    authority_checked = models.BooleanField(
        "Đã được người có thẩm quyền kiểm tra nội dung",
        default=False,
        editable=False,
        help_text="Chỉ người có quyền duyệt mới xác nhận. Hệ thống không tự khẳng định tài liệu đáp ứng quy định.",
    )
    authority_checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False
    )
    authority_note = models.CharField("Ghi chú kiểm tra", max_length=500, blank=True, editable=False)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["section__order", "-disclosure_date", "-created_at"]
        verbose_name = "Công khai giáo dục"
        verbose_name_plural = "Công khai giáo dục"

    def __str__(self):
        return self.title

    def publish_blockers(self):
        if not self.authority_checked:
            return ["Nội dung công khai chưa được người có thẩm quyền xác nhận đã kiểm tra."]
        return []

    @property
    def review_state(self):
        if not self.review_due:
            return ""
        from apps.core.models import SiteSettings

        today = timezone.localdate()
        if self.review_due < today:
            return "overdue"
        if (self.review_due - today).days <= SiteSettings.load().disclosure_review_days:
            return "soon"
        return ""


class DisclosureVersion(models.Model):
    disclosure = models.ForeignKey(Disclosure, on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveIntegerField("Phiên bản")
    file = models.FileField("Tệp", upload_to=UniqueUploadPath("disclosures/history"), storage=get_protected_storage, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    note = models.CharField("Ghi chú cập nhật", max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-version_no"]
        constraints = [models.UniqueConstraint(fields=["disclosure", "version_no"], name="uniq_disclosure_version")]
        verbose_name = "Lịch sử công khai"
        verbose_name_plural = "Lịch sử công khai"

    def __str__(self):
        return f"{self.disclosure} v{self.version_no}"
