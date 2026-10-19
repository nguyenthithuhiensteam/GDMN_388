"""Ghi nhật ký thao tác."""
from django.forms.models import model_to_dict


def client_ip(request):
    if request is None:
        return None
    from django.conf import settings

    # Chỉ tin header X-Real-IP khi chạy sau reverse proxy đáng tin (TRUST_X_REAL_IP=True).
    if settings.TRUST_X_REAL_IP and request.META.get("HTTP_X_REAL_IP"):
        return request.META["HTTP_X_REAL_IP"]
    return request.META.get("REMOTE_ADDR") or None


def log_action(request_or_user, action, obj=None, module="", changes=None, object_repr=None, user=None):
    from .models import AuditLog

    request = None
    if hasattr(request_or_user, "META"):
        request = request_or_user
        user = user or getattr(request, "user", None)
    else:
        user = user or request_or_user
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return AuditLog.objects.create(
        user=user,
        action=action,
        module=module,
        object_type=obj._meta.label if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
        object_repr=(object_repr or (str(obj) if obj is not None else ""))[:255],
        changes=changes or {},
        ip_address=client_ip(request),
    )


def diff_instances(before, after, fields=None):
    """So sánh 2 dict model_to_dict, trả về {field: [cũ, mới]} (rút gọn chuỗi dài)."""
    changes = {}
    for key, new in after.items():
        if fields and key not in fields:
            continue
        old = before.get(key)
        if old != new:
            changes[key] = [_short(old), _short(new)]
    return changes


def snapshot(obj):
    data = model_to_dict(obj)
    return {k: (str(v) if not isinstance(v, (int, float, bool, type(None))) else v) for k, v in data.items()}


def _short(v):
    s = v if isinstance(v, (int, float, bool, type(None))) else str(v)
    if isinstance(s, str) and len(s) > 200:
        return s[:200] + "…"
    return s
