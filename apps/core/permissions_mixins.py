"""Mixin/decorator kiểm tra quyền phía máy chủ cho view."""
from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import has_full_scope, has_perm


def require_perm(module, action):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_perm(request.user, module, action):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


class ModulePermissionMixin(LoginRequiredMixin):
    module = None
    action = "view"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not has_perm(request.user, self.module, self.action):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def owns_or_scoped(user, obj, owner_field="created_by"):
    """Quyền theo đối tượng: toàn trường; hoặc là người tạo; hoặc tổ trưởng cùng tổ."""
    if has_full_scope(user):
        return True
    if getattr(obj, f"{owner_field}_id", None) == user.pk:
        return True
    from apps.accounts.permissions import ROLE_GROUP_LEADER

    group_id = getattr(obj, "group_id", None)
    return user.role == ROLE_GROUP_LEADER and group_id is not None and group_id == user.group_id
