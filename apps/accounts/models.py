from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .permissions import ACTIONS, MODULES, ROLE_CHOICES, ROLE_LABELS, ROLE_TEACHER


class User(AbstractUser):
    """Tài khoản cán bộ, giáo viên, nhân viên. Không dùng cho trẻ hoặc phụ huynh."""

    full_name = models.CharField("Họ và tên", max_length=150)
    role = models.CharField("Vai trò", max_length=20, choices=ROLE_CHOICES, default=ROLE_TEACHER, db_index=True)
    position = models.CharField("Chức vụ", max_length=150, blank=True)
    phone = models.CharField("Điện thoại", max_length=30, blank=True)
    campus = models.ForeignKey(
        "org.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Điểm trường",
        related_name="users",
    )
    group = models.ForeignKey(
        "org.ProfessionalGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tổ chuyên môn",
        related_name="members",
    )
    classes = models.ManyToManyField("org.SchoolClass", blank=True, verbose_name="Lớp phụ trách", related_name="teachers")
    must_change_password = models.BooleanField("Bắt buộc đổi mật khẩu", default=False)
    locked_reason = models.CharField("Lý do khóa", max_length=255, blank=True)

    class Meta:
        ordering = ["full_name", "username"]
        verbose_name = "Tài khoản"
        verbose_name_plural = "Tài khoản"

    def __str__(self):
        return self.full_name or self.username

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    def get_full_name(self):
        return self.full_name or self.username

    def can(self, module, action):
        from .permissions import has_perm

        return has_perm(self, module, action)


class RolePermission(models.Model):
    role = models.CharField("Vai trò", max_length=20, choices=ROLE_CHOICES)
    module = models.CharField("Chức năng", max_length=40, choices=[(k, v[0]) for k, v in MODULES.items()])
    action = models.CharField("Thao tác", max_length=20, choices=ACTIONS)
    allowed = models.BooleanField("Được phép", default=False)

    class Meta:
        verbose_name = "Quyền theo vai trò"
        verbose_name_plural = "Ma trận phân quyền"
        constraints = [models.UniqueConstraint(fields=["role", "module", "action"], name="uniq_role_module_action")]
        indexes = [models.Index(fields=["role", "allowed"])]

    def __str__(self):
        return f"{self.role}:{self.module}:{self.action}={self.allowed}"


class LoginAttempt(models.Model):
    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lần đăng nhập"
        verbose_name_plural = "Lịch sử đăng nhập"

    def __str__(self):
        return f"{self.username} {self.created_at:%d/%m/%Y %H:%M} {'OK' if self.successful else 'FAIL'}"


class UserSession(models.Model):
    """Theo dõi phiên đăng nhập để người dùng/quản trị có thể thu hồi phiên."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tracked_sessions")
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-last_seen"]
        verbose_name = "Phiên đăng nhập"
        verbose_name_plural = "Phiên đăng nhập"

    def __str__(self):
        return f"{self.user} {self.ip_address or ''}"
