from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.crud import AdminCreateView, AdminDeleteView, AdminListView, AdminUpdateView
from apps.core.permissions_mixins import require_perm

from .forms import LockForm, LoginForm, ProfileForm, UserAdminForm
from .models import RolePermission, User, UserSession
from .permissions import ACTION_LABELS, MODULES, ROLE_ADMIN, ROLE_CHOICES


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["revoked"] = self.request.GET.get("revoked") == "1"
        return ctx


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("core:dashboard")

    def get_form(self, form_class=None):
        from apps.core.forms_base import style_fields

        form = super().get_form(form_class)
        style_fields(form)
        return form

    def form_valid(self, form):
        old_key = self.request.session.session_key
        response = super().form_valid(form)  # đổi khóa phiên (cycle_key)
        _follow_session_key(old_key, self.request.session.session_key)
        user = form.user
        if user.must_change_password:
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
        # Thu hồi các phiên khác sau khi đổi mật khẩu
        _revoke_sessions(user, keep=self.request.session.session_key)
        log_action(self.request, "password_change", user, module="user")
        messages.success(self.request, "Đã đổi mật khẩu. Các phiên đăng nhập khác đã được đăng xuất.")
        return response


def _follow_session_key(old_key, new_key):
    """Giữ phiên đang theo dõi khi Django đổi khóa phiên (sau đổi mật khẩu)."""
    if old_key and new_key and old_key != new_key:
        UserSession.objects.filter(session_key=old_key).update(session_key=new_key)


def _revoke_sessions(user, keep=None):
    count = 0
    for s in UserSession.objects.filter(user=user):
        if keep and s.session_key == keep:
            continue
        SessionStore(session_key=s.session_key).delete()
        s.delete()
        count += 1
    return count


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "profile_update", request.user, module="user")
        messages.success(request, "Đã cập nhật hồ sơ cá nhân.")
        return redirect("accounts:profile")
    sessions = UserSession.objects.filter(user=request.user)
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "sessions": sessions,
            "current_key": request.session.session_key,
        },
    )


@login_required
@require_POST
def revoke_session(request, pk):
    s = get_object_or_404(UserSession, pk=pk, user=request.user)
    if s.session_key == request.session.session_key:
        messages.info(request, "Dùng nút Đăng xuất để kết thúc phiên hiện tại.")
    else:
        SessionStore(session_key=s.session_key).delete()
        s.delete()
        log_action(request, "session_revoke", request.user, module="user")
        messages.success(request, "Đã đăng xuất phiên được chọn.")
    return redirect("accounts:profile")


@login_required
@require_POST
def revoke_other_sessions(request):
    n = _revoke_sessions(request.user, keep=request.session.session_key)
    log_action(request, "session_revoke_all", request.user, module="user", changes={"count": n})
    messages.success(request, f"Đã đăng xuất {n} phiên khác.")
    return redirect("accounts:profile")


# --- Quản lý tài khoản ---------------------------------------------------------


def _guard_target(actor, target):
    """Chỉ Quản trị hệ thống được sửa tài khoản Quản trị hệ thống/superuser."""
    if (target.role == ROLE_ADMIN or target.is_superuser) and not (actor.is_superuser or actor.role == ROLE_ADMIN):
        raise PermissionDenied


class UserList(AdminListView):
    model = User
    module = "user"
    page_title = "Tài khoản người dùng"
    url_prefix = "users:user"
    template_name = "accounts/user_list.html"
    search_fields = ["username", "full_name", "email"]
    filter_fields = ["role", "campus", "group", "is_active"]

    def get_queryset(self):
        return super().get_queryset().select_related("campus", "group")


class UserCreate(AdminCreateView):
    model = User
    form_class = UserAdminForm
    module = "user"
    page_title = "Tạo tài khoản"
    url_prefix = "users:user"
    success_message = "Đã tạo tài khoản. Hãy gửi mật khẩu tạm thời cho người dùng qua kênh an toàn."


class UserUpdate(AdminUpdateView):
    model = User
    form_class = UserAdminForm
    module = "user"
    page_title = "Sửa tài khoản"
    url_prefix = "users:user"

    def can_modify(self, obj):
        _guard_target(self.request.user, obj)
        return True

    def after_save(self, form, obj, created):
        is_self = obj.pk == self.request.user.pk
        if form.cleaned_data.get("password1") or not obj.is_active:
            _revoke_sessions(obj, keep=self.request.session.session_key if is_self else None)
            if is_self:
                old_key = self.request.session.session_key
                update_session_auth_hash(self.request, obj)
                _follow_session_key(old_key, self.request.session.session_key)


class UserDelete(AdminDeleteView):
    model = User
    module = "user"
    page_title = "Xóa tài khoản"
    url_prefix = "users:user"

    def can_modify(self, obj):
        _guard_target(self.request.user, obj)
        if obj.pk == self.request.user.pk:
            raise PermissionDenied
        return True


@require_perm("user", "edit")
def user_toggle_lock(request, pk):
    target = get_object_or_404(User, pk=pk)
    _guard_target(request.user, target)
    if target.pk == request.user.pk:
        raise PermissionDenied
    form = LockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            target.is_active = not target.is_active
            target.locked_reason = "" if target.is_active else form.cleaned_data["reason"]
            target.save(update_fields=["is_active", "locked_reason"])
            if not target.is_active:
                _revoke_sessions(target)
        log_action(
            request, "unlock" if target.is_active else "lock", target, module="user", changes={"reason": form.cleaned_data["reason"]}
        )
        messages.success(request, ("Đã mở khóa " if target.is_active else "Đã khóa ") + str(target))
        return redirect("users:user_list")
    return render(request, "accounts/user_lock.html", {"target": target, "form": form})


# --- Ma trận phân quyền ------------------------------------------------------------


@require_perm("settings", "view")
def permission_matrix(request):
    can_edit = request.user.is_superuser or request.user.role == ROLE_ADMIN
    editable_roles = [r for r in ROLE_CHOICES if r[0] != ROLE_ADMIN]
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        changed = []
        for perm in RolePermission.objects.exclude(role=ROLE_ADMIN):
            key = f"p__{perm.role}__{perm.module}__{perm.action}"
            new = key in request.POST
            if perm.allowed != new:
                perm.allowed = new
                perm.save(update_fields=["allowed"])
                changed.append([perm.role, perm.module, perm.action, new])
        log_action(request, "permission_matrix_update", None, module="settings", changes={"changed": changed})
        messages.success(request, f"Đã cập nhật {len(changed)} quyền.")
        return redirect("users:permissions")
    allowed = set(RolePermission.objects.filter(allowed=True).values_list("role", "module", "action"))
    rows = []
    for module, (label, acts) in MODULES.items():
        for action in acts:
            rows.append(
                {
                    "module": module,
                    "module_label": label,
                    "action": action,
                    "action_label": ACTION_LABELS[action],
                    "cells": [{"role": r, "checked": (r, module, action) in allowed} for r, _ in editable_roles],
                }
            )
    return render(
        request,
        "accounts/permission_matrix.html",
        {
            "rows": rows,
            "roles": editable_roles,
            "can_edit_matrix": can_edit,
        },
    )
