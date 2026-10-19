import datetime as dt

from django import template
from django.db.models import Model
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.core.workflow import STATUS_BADGES

register = template.Library()


@register.simple_tag
def cell(obj, attr):
    """Hiển thị giá trị một cột trong bảng quản trị."""
    if attr == "status" and hasattr(obj, "get_status_display"):
        badge = getattr(obj, "status_badge", None) or STATUS_BADGES.get(obj.status, "secondary")
        label = getattr(obj, "display_status", None) or obj.get_status_display()
        return format_html('<span class="badge text-bg-{}">{}</span>', badge, label)
    display = getattr(obj, f"get_{attr}_display", None)
    if callable(display):
        return display()
    value = getattr(obj, attr, "")
    if callable(value) and not isinstance(value, Model):
        value = value()
    if isinstance(value, bool):
        return format_html('<i class="bi {}" aria-label="{}"></i>',
                           "bi-check-circle-fill text-success" if value else "bi-dash text-muted",
                           "Có" if value else "Không")
    if isinstance(value, dt.datetime):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M") if timezone.is_aware(value) else value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, dt.date):
        return value.strftime("%d/%m/%Y")
    if value is None:
        return "—"
    text = str(value)
    return text if len(text) <= 90 else text[:90] + "…"


@register.simple_tag
def row_url(url_prefix, suffix, obj=None, entity=None):
    if url_prefix == "org":
        kwargs = {"entity": entity}
        if obj is not None:
            kwargs["pk"] = obj.pk
        return reverse(f"org:{suffix}", kwargs=kwargs)
    if obj is not None:
        return reverse(f"{url_prefix}_{suffix}", args=[obj.pk])
    return reverse(f"{url_prefix}_{suffix}")


@register.filter
def filesize(num):
    try:
        num = float(num)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


@register.filter
def get_item(d, key):
    try:
        return d[key]
    except (KeyError, TypeError, IndexError):
        return None


@register.filter
def basename(path):
    return str(path).rsplit("/", 1)[-1]


@register.simple_tag(takes_context=True)
def qs_no_page(context):
    """Chuỗi truy vấn hiện tại bỏ tham số page (dùng cho phân trang)."""
    request = context.get("request")
    if request is None:
        return ""
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()
