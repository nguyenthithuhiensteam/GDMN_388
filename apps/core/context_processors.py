from django.db.utils import DatabaseError

from apps.accounts.permissions import MODULES, has_perm


class _PermProxy:
    """Cho phép dùng {{ perms_ui.news.create }} trong template (chỉ để ẩn/hiện; máy chủ vẫn kiểm tra)."""

    def __init__(self, user):
        self.user = user

    def __getitem__(self, module):
        user = self.user

        class _Acts:
            def __getitem__(self, action):
                return has_perm(user, module, action)

            __getattr__ = __getitem__

        return _Acts()

    __getattr__ = __getitem__


def site(request):
    from .models import Notification, SiteSettings

    try:
        settings_obj = SiteSettings.load()
    except DatabaseError:  # pragma: no cover - trước khi migrate
        settings_obj = SiteSettings()
    ctx = {"school": settings_obj}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and request.path.startswith(("/quan-tri", "/tai-khoan")):
        ctx["perms_ui"] = _PermProxy(user)
        ctx["unread_notifications"] = Notification.objects.filter(user=user, is_read=False).count()
        ctx["module_labels"] = {k: v[0] for k, v in MODULES.items()}
    return ctx
