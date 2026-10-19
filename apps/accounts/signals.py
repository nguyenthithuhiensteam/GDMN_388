from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone

from apps.core.audit import client_ip, log_action

from .models import RolePermission, UserSession
from .permissions import default_allowed, iter_matrix_keys


def ensure_permission_matrix(**kwargs):
    """Nạp các ô còn thiếu của ma trận quyền theo giá trị mặc định (không ghi đè ô đã chỉnh)."""
    existing = set(RolePermission.objects.values_list("role", "module", "action"))
    missing = [
        RolePermission(role=r, module=m, action=a, allowed=default_allowed(r, m, a))
        for r, m, a in iter_matrix_keys()
        if (r, m, a) not in existing
    ]
    if missing:
        RolePermission.objects.bulk_create(missing, ignore_conflicts=True)


@receiver(post_migrate)
def _seed_after_migrate(sender, **kwargs):
    if sender.name == "apps.accounts":
        ensure_permission_matrix()


@receiver(user_logged_in)
def _track_login(sender, request, user, **kwargs):
    if request is None or not hasattr(request, "session"):
        return
    if not request.session.session_key:
        request.session.save()
    UserSession.objects.update_or_create(
        session_key=request.session.session_key,
        defaults={
            "user": user,
            "ip_address": client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
            "created_at": timezone.now(),
            "last_seen": timezone.now(),
        },
    )
    log_action(request, "login", user, module="user", user=user)


@receiver(user_logged_out)
def _track_logout(sender, request, user, **kwargs):
    if request is not None and getattr(request, "session", None) and request.session.session_key:
        UserSession.objects.filter(session_key=request.session.session_key).delete()
    if user is not None and request is not None:
        log_action(user, "logout", user, module="user")
