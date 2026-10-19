from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from apps.core.audit import client_ip
from apps.core.forms_base import BaseModelForm, style_fields

from .models import LoginAttempt, User
from .permissions import ROLE_ADMIN, ROLE_CHOICES, is_last_active_admin


def is_locked(username, ip):
    window = timezone.now() - timezone.timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    recent = LoginAttempt.objects.filter(created_at__gte=window)
    last_ok = recent.filter(username__iexact=username, successful=True).order_by("-created_at").first()
    user_fail = recent.filter(username__iexact=username, successful=False)
    if last_ok:
        user_fail = user_fail.filter(created_at__gt=last_ok.created_at)
    if user_fail.count() >= settings.LOGIN_MAX_FAILURES:
        return True
    if ip and recent.filter(ip_address=ip, successful=False).count() >= settings.LOGIN_MAX_FAILURES * 4:
        return True
    return False


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Tên đăng nhập hoặc mật khẩu không đúng.",
        "inactive": "Tài khoản đã bị khóa. Vui lòng liên hệ quản trị hệ thống.",
        "locked": "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau %(minutes)s phút.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Tên đăng nhập"
        self.fields["password"].label = "Mật khẩu"
        style_fields(self)

    def clean(self):
        username = (self.cleaned_data.get("username") or "").strip()
        ip = client_ip(self.request)
        if username and is_locked(username, ip):
            raise forms.ValidationError(
                self.error_messages["locked"],
                code="locked",
                params={"minutes": settings.LOGIN_LOCKOUT_MINUTES},
            )
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            LoginAttempt.objects.create(username=username[:150], ip_address=ip, successful=False)
            raise
        LoginAttempt.objects.create(username=username[:150], ip_address=ip, successful=True)
        return cleaned


class ProfileForm(BaseModelForm):
    class Meta:
        model = User
        fields = ["full_name", "email", "phone"]


def _role_choices_for(actor):
    if actor.is_superuser or actor.role == ROLE_ADMIN:
        return ROLE_CHOICES
    return [c for c in ROLE_CHOICES if c[0] != ROLE_ADMIN]


class UserAdminForm(BaseModelForm):
    """Form quản lý tài khoản. Người dùng không thể tự đổi vai trò/trạng thái của chính mình."""

    password1 = forms.CharField(
        label="Mật khẩu tạm thời",
        widget=forms.PasswordInput,
        required=False,
        help_text="Người dùng sẽ phải đổi mật khẩu ở lần đăng nhập đầu tiên.",
    )
    password2 = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ["username", "full_name", "email", "phone", "role", "position", "campus", "group", "classes", "is_active"]
        widgets = {"classes": forms.SelectMultiple(attrs={"size": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = _role_choices_for(self.user)
        self.fields["is_active"].label = "Đang hoạt động"
        creating = not self.instance.pk
        self.fields["password1"].required = creating
        self.fields["password2"].required = creating
        if not creating:
            self.fields["password1"].help_text = "Để trống nếu không đặt lại mật khẩu."
        if self.instance.pk and self.instance.pk == self.user.pk:
            # Không cho tự nâng quyền hoặc tự khóa tài khoản của mình.
            self.fields["role"].disabled = True
            self.fields["is_active"].disabled = True

    def clean_role(self):
        role = self.cleaned_data["role"]
        allowed = {c[0] for c in _role_choices_for(self.user)}
        if role not in allowed:
            raise forms.ValidationError("Bạn không có quyền gán vai trò này.")
        return role

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            original = User.objects.get(pk=self.instance.pk)
            demoted = cleaned.get("role", original.role) != ROLE_ADMIN or not cleaned.get("is_active", original.is_active)
            if demoted and is_last_active_admin(original):
                raise forms.ValidationError(
                    "Đây là tài khoản Quản trị hệ thống duy nhất đang hoạt động: không thể khóa hoặc đổi vai trò. "
                    "Hãy tạo thêm một tài khoản Quản trị trước."
                )
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Mật khẩu nhập lại không khớp.")
            else:
                try:
                    password_validation.validate_password(p1, self.instance)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
            user.must_change_password = True
        if commit:
            user.save()
            self.save_m2m()
        return user


class LockForm(forms.Form):
    reason = forms.CharField(label="Lý do", max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
