from django.conf import settings
from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .validators import validate_image_upload

hex_color = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Mã màu dạng #RRGGBB.")


class SiteSettings(models.Model):
    """Cấu hình hiển thị của trường (bản ghi duy nhất). Sửa tại /quan-tri/cau-hinh/."""

    school_name = models.CharField("Tên trường", max_length=200, default="TRƯỜNG MẦM NON [TÊN TRƯỜNG]")
    short_name = models.CharField("Tên viết tắt", max_length=60, blank=True, default="MN")
    governing_body = models.CharField("Cơ quan chủ quản", max_length=200, blank=True)
    slogan = models.CharField("Khẩu hiệu", max_length=255, blank=True)
    logo = models.ImageField("Logo", upload_to="site/", blank=True, validators=[validate_image_upload])
    banner = models.ImageField("Ảnh banner trang chủ", upload_to="site/", blank=True, validators=[validate_image_upload])
    banner_title = models.CharField("Tiêu đề banner", max_length=200, blank=True, default="Nơi mỗi ngày đến trường là một ngày vui")
    banner_text = models.TextField("Nội dung banner", blank=True)
    address = models.CharField("Địa chỉ", max_length=255, blank=True)
    phone = models.CharField("Điện thoại", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    website_domain = models.CharField("Tên miền", max_length=150, blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    map_embed_url = models.URLField(
        "URL nhúng bản đồ",
        blank=True,
        max_length=1000,
        help_text="Chỉ dán đường dẫn trong thuộc tính src của mã nhúng Google Maps (https://www.google.com/maps/embed?...).",
    )
    working_hours = models.CharField("Giờ làm việc", max_length=200, blank=True)
    intro_text = models.TextField("Giới thiệu ngắn (trang chủ)", blank=True)
    program_text = models.TextField("Chương trình giáo dục (trang chủ)", blank=True)
    admission_text = models.TextField("Thông tin tuyển sinh (trang chủ)", blank=True)
    color_primary = models.CharField("Màu chính (xanh lá)", max_length=7, default="#3A9A3E", validators=[hex_color])
    color_accent = models.CharField("Màu nhấn (vàng)", max_length=7, default="#F5C518", validators=[hex_color])
    color_secondary = models.CharField("Màu phụ (xanh dương)", max_length=7, default="#1A6BDB", validators=[hex_color])
    color_dark = models.CharField("Màu đậm", max_length=7, default="#0A1F4E", validators=[hex_color])
    require_approval = models.BooleanField(
        "Bắt buộc duyệt trước khi xuất bản",
        default=True,
        help_text="Nếu bật, nội dung phải ở trạng thái 'Đã duyệt' mới được xuất bản.",
    )
    disclosure_review_days = models.PositiveIntegerField(
        "Nhắc rà soát công khai trước (ngày)",
        default=30,
    )
    footer_note = models.CharField("Ghi chú chân trang", max_length=255, blank=True)
    demo_data_loaded = models.BooleanField("Đang chứa dữ liệu mẫu", default=False, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    CACHE_KEY = "site_settings"

    class Meta:
        verbose_name = "Cấu hình trường"
        verbose_name_plural = "Cấu hình trường"

    def __str__(self):
        return self.school_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj


class AuditLog(models.Model):
    """Nhật ký thao tác quan trọng (tạo/sửa/xóa/duyệt/xuất bản/xuất dữ liệu/đăng nhập...)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Người thực hiện",
        related_name="audit_logs",
    )
    action = models.CharField("Thao tác", max_length=50, db_index=True)
    module = models.CharField("Chức năng", max_length=40, blank=True, db_index=True)
    object_type = models.CharField("Loại đối tượng", max_length=100, blank=True)
    object_id = models.CharField("Mã đối tượng", max_length=50, blank=True, db_index=True)
    object_repr = models.CharField("Đối tượng", max_length=255, blank=True)
    changes = models.JSONField("Thay đổi", default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField("Thời điểm", default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Nhật ký"
        verbose_name_plural = "Nhật ký hệ thống"
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def __str__(self):
        return f"{self.created_at:%d/%m/%Y %H:%M} {self.user} {self.action} {self.object_repr}"


class Notification(models.Model):
    """Thông báo nhắc việc hiển thị trên giao diện quản trị."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField("Nội dung", max_length=255)
    url = models.CharField("Liên kết", max_length=255, blank=True)
    is_read = models.BooleanField("Đã đọc", default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Thông báo nội bộ"
        verbose_name_plural = "Thông báo nội bộ"

    def __str__(self):
        return self.message


class ContactMessage(models.Model):
    STATUS = [("new", "Mới"), ("processing", "Đang xử lý"), ("done", "Đã phản hồi")]
    name = models.CharField("Họ tên", max_length=150)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Điện thoại", max_length=30, blank=True)
    subject = models.CharField("Tiêu đề", max_length=200)
    message = models.TextField("Nội dung", max_length=3000)
    status = models.CharField("Trạng thái", max_length=20, choices=STATUS, default="new")
    note = models.TextField("Ghi chú xử lý", blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField("Thời điểm gửi", default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Liên hệ"
        verbose_name_plural = "Liên hệ"

    def __str__(self):
        return f"{self.name}: {self.subject}"
