"""
Các khối (panel) dashboard riêng theo vai trò. Mỗi khối chỉ được tạo khi người dùng có quyền tương ứng
và dữ liệu luôn lọc theo phạm vi người dùng được phép xem.

Một khối: {"key", "title", "icon", "items": [{"text", "url", "badge", "style", "sub"}], "empty", "more_url"}
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import (
    MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_GROUP_LEADER,
    ROLE_OFFICE,
    has_perm,
)


def _panel(key, title, icon, items, empty, more_url=None):
    return {"key": key, "title": title, "icon": icon, "items": items, "empty": empty, "more_url": more_url}


def _item(text, url="", badge="", style="secondary", sub=""):
    return {"text": text, "url": url, "badge": badge, "style": style, "sub": sub}


def is_admin(user):
    return user.is_superuser or user.role == ROLE_ADMIN


# --- Quản trị hệ thống ----------------------------------------------------------------------
def system_health_panel(user):
    from apps.accounts.models import LoginAttempt, User, UserSession

    now = timezone.now()
    failed_24h = LoginAttempt.objects.filter(successful=False, created_at__gte=now - timedelta(hours=24)).count()
    locked = User.objects.filter(is_active=False).count()
    must_change = User.objects.filter(is_active=True, must_change_password=True).count()
    active_admins = User.objects.filter(Q(role=ROLE_ADMIN) | Q(is_superuser=True), is_active=True).count()
    users_url = reverse("users:user_list")
    items = [
        _item("Đăng nhập thất bại trong 24 giờ", users_url, failed_24h, "danger" if failed_24h >= 10 else "secondary"),
        _item("Tài khoản đang bị khóa", users_url + "?is_active=False", locked, "warning" if locked else "secondary"),
        _item("Tài khoản chưa đổi mật khẩu tạm", users_url, must_change, "warning" if must_change else "secondary"),
        _item("Phiên đăng nhập đang theo dõi", "", UserSession.objects.count()),
        _item(
            "Số tài khoản Quản trị hệ thống đang hoạt động",
            users_url + f"?role={ROLE_ADMIN}",
            active_admins,
            "warning" if active_admins < 2 else "success",
            "Nên có ít nhất 2 tài khoản quản trị để dự phòng." if active_admins < 2 else "",
        ),
    ]
    backup_dir = Path(settings.BACKUP_DIR)
    backups = sorted(backup_dir.glob("backup-*.zip")) if backup_dir.exists() else []
    if backups:
        age = now - datetime.fromtimestamp(backups[-1].stat().st_mtime, tz=UTC)
        days = age.days
        items.append(_item("Bản sao lưu gần nhất", reverse("core:settings"), f"{days} ngày trước", "danger" if days > 2 else "success"))
    else:
        items.append(_item("Bản sao lưu gần nhất", reverse("core:settings"), "Chưa có", "danger", "Chạy: python manage.py backup_data"))
    if settings.DEBUG:
        items.append(_item("Chế độ DEBUG đang bật", "", "Chỉ dùng khi phát triển", "warning"))
    return _panel("system", "Tình trạng hệ thống", "shield-check", items, "")


def failed_logins_panel(user):
    from apps.accounts.models import LoginAttempt

    rows = LoginAttempt.objects.filter(successful=False)[:8]
    items = [_item(a.username, "", a.created_at.strftime("%d/%m %H:%M"), "danger", a.ip_address or "") for a in rows]
    return _panel("failed_logins", "Đăng nhập thất bại gần đây", "exclamation-octagon", items, "Không có đăng nhập thất bại.")


# --- Lãnh đạo ----------------------------------------------------------------------------------
def approval_queue_panel(user):
    from apps.content.models import Album, Announcement, Disclosure, Post
    from apps.core.workflow import Status
    from apps.office.models import EducationPlan
    from apps.office.views import can_approve_plan

    items = []
    sources = [
        ("news", Post, "Tin bài", "content:news_detail"),
        ("announcement", Announcement, "Thông báo", "content:announcement_detail"),
        ("album", Album, "Album", "content:album_detail"),
        ("disclosure", Disclosure, "Công khai", "content:disclosure_detail"),
    ]
    for module, model, label, url_name in sources:
        if has_perm(user, module, "approve"):
            for obj in model.objects.filter(status=Status.PENDING).order_by("updated_at")[:5]:
                items.append(_item(obj.title, reverse(url_name, args=[obj.pk]), label, "warning", f"Gửi lúc {obj.updated_at:%d/%m/%Y}"))
    if has_perm(user, "plan", "approve"):
        for plan in EducationPlan.objects.filter(status="pending").select_related("group")[:20]:
            if can_approve_plan(user, plan):
                items.append(
                    _item(plan.title, reverse("office:plan_detail", args=[plan.pk]), "Kế hoạch", "primary", plan.get_level_display())
                )
    return _panel("approvals", "Hàng chờ phê duyệt", "check2-square", items[:12], "Không có nội dung chờ duyệt.")


def group_progress_panel(user, group_id=None):
    from apps.office.models import Task

    today = timezone.localdate()
    qs = Task.objects.for_user(user).exclude(assigned_group=None)
    if group_id:
        qs = qs.filter(assigned_group_id=group_id)
    rows = (
        qs.values("assigned_group__name")
        .annotate(
            total=Count("pk"),
            done=Count("pk", filter=Q(status="done")),
            overdue=Count("pk", filter=Q(due_date__lt=today) & ~Q(status="done")),
        )
        .order_by("assigned_group__name")
    )
    items = []
    for r in rows:
        pct = round(100 * r["done"] / r["total"]) if r["total"] else 0
        sub = f"{r['done']}/{r['total']} hoàn thành" + (f" · {r['overdue']} quá hạn" if r["overdue"] else "")
        items.append(_item(r["assigned_group__name"], reverse("office:task_list"), f"{pct}%", "danger" if r["overdue"] else "success", sub))
    return _panel("group_progress", "Tiến độ nhiệm vụ theo tổ", "bar-chart-steps", items, "Chưa có nhiệm vụ giao cho tổ.")


# --- Văn phòng -------------------------------------------------------------------------------
def documents_to_process_panel(user):
    from apps.office.models import OfficialDocument

    docs = (
        OfficialDocument.objects.for_user(user).filter(processing_status__in=["new", "processing"]).order_by("deadline", "-issue_date")[:8]
    )
    items = []
    for d in docs:
        style = "danger" if d.is_overdue else "secondary"
        badge = d.deadline.strftime("%d/%m/%Y") if d.deadline else d.get_processing_status_display()
        items.append(_item(str(d), reverse("office:doc_detail", args=[d.pk]), badge, style, str(d.responsible or "Chưa giao")))
    return _panel("docs", "Văn bản cần xử lý", "folder2-open", items, "Không có văn bản đang chờ xử lý.", reverse("office:doc_list"))


def contact_panel(user):
    from apps.core.models import ContactMessage

    items = [
        _item(m.subject, reverse("core:contact_detail", args=[m.pk]), m.created_at.strftime("%d/%m"), "info", m.name)
        for m in ContactMessage.objects.filter(status="new")[:6]
    ]
    return _panel("contacts", "Liên hệ mới", "chat-dots", items, "Không có liên hệ mới.", reverse("core:contact_list"))


# --- Tổ trưởng --------------------------------------------------------------------------------
def my_group_panel(user):
    from apps.accounts.models import User
    from apps.office.models import EducationPlan, Task

    if not user.group_id:
        return _panel("my_group", "Tổ của tôi", "people", [], "Tài khoản chưa được gán tổ chuyên môn.")
    today = timezone.localdate()
    members = User.objects.filter(group_id=user.group_id, is_active=True)
    items = [_item("Thành viên đang hoạt động", "", members.count())]
    pending = EducationPlan.objects.filter(group_id=user.group_id, status="pending")
    items.append(
        _item(
            "Kế hoạch của tổ chờ tôi duyệt",
            reverse("office:plan_list") + "?status=pending",
            pending.count(),
            "warning" if pending.exists() else "secondary",
        )
    )
    late = (
        Task.objects.filter(Q(assignee__group_id=user.group_id) | Q(assigned_group_id=user.group_id))
        .filter(due_date__lt=today)
        .exclude(status="done")
    )
    items.append(
        _item(
            "Nhiệm vụ quá hạn trong tổ",
            reverse("office:task_list") + "?xem=qua-han",
            late.count(),
            "danger" if late.exists() else "secondary",
        )
    )
    return _panel("my_group", f"Tổ của tôi: {user.group}", "people", items, "")


# --- Mọi người dùng ------------------------------------------------------------------------
def my_tasks_panel(user):
    from apps.office.models import Task

    qs = Task.objects.for_user(user).filter(Q(assignee=user) | Q(assignee__isnull=True, assigned_group_id=user.group_id))
    items = []
    for t in qs.open().order_by("due_date")[:8]:
        badge = t.due_date.strftime("%d/%m/%Y") if t.due_date else t.display_status
        items.append(_item(t.title, reverse("office:task_detail", args=[t.pk]), badge, t.status_badge, t.display_status))
    return _panel(
        "my_tasks", "Việc của tôi", "list-check", items, "Bạn không có việc đang mở.", reverse("office:task_list") + "?xem=cua-toi"
    )


def my_plans_panel(user):
    from apps.office.models import EducationPlan

    items = []
    for p in EducationPlan.objects.filter(created_by=user).exclude(status="archived").order_by("-updated_at")[:6]:
        items.append(_item(p.title, reverse("office:plan_detail", args=[p.pk]), p.get_status_display(), p.status_badge))
    return _panel("my_plans", "Kế hoạch tôi lập", "journal-text", items, "Bạn chưa lập kế hoạch nào.", reverse("office:plan_list"))


def my_content_panel(user):
    from apps.content.models import Album, Announcement, Post
    from apps.core.workflow import STATUS_BADGES, Status

    items = []
    for module, model, url_name in (
        ("news", Post, "content:news_detail"),
        ("announcement", Announcement, "content:announcement_detail"),
        ("album", Album, "content:album_detail"),
    ):
        if not has_perm(user, module, "view"):
            continue
        for obj in model.objects.filter(created_by=user, status__in=[Status.DRAFT, Status.PENDING, Status.APPROVED])[:4]:
            sub = f"Ghi chú duyệt: {obj.review_note}" if obj.review_note else ""
            items.append(_item(obj.title, reverse(url_name, args=[obj.pk]), obj.get_status_display(), STATUS_BADGES[obj.status], sub))
    return _panel("my_content", "Nội dung tôi soạn chưa xuất bản", "pencil-square", items, "Không có nội dung đang soạn.")


def panels_for(user):
    """Chọn khối theo vai trò, sau đó kiểm tra quyền của từng khối."""
    panels = []
    if is_admin(user):
        panels += [system_health_panel(user), failed_logins_panel(user)]
    if (user.role in MANAGER_ROLES or is_admin(user)) and any(
        has_perm(user, m, "approve") for m in ("news", "announcement", "album", "disclosure", "plan")
    ):
        panels.append(approval_queue_panel(user))
    if user.role in MANAGER_ROLES and has_perm(user, "task", "view"):
        panels.append(group_progress_panel(user))
    if user.role == ROLE_OFFICE or user.role in MANAGER_ROLES:
        if has_perm(user, "official_doc", "view"):
            panels.append(documents_to_process_panel(user))
        if has_perm(user, "contact", "view"):
            panels.append(contact_panel(user))
    if user.role == ROLE_GROUP_LEADER:
        panels.append(my_group_panel(user))
        if has_perm(user, "plan", "approve"):
            panels.append(approval_queue_panel(user))
        if has_perm(user, "task", "view") and user.group_id:
            panels.append(group_progress_panel(user, user.group_id))
    if has_perm(user, "task", "view"):
        panels.append(my_tasks_panel(user))
    if has_perm(user, "plan", "create"):
        panels.append(my_plans_panel(user))
    if any(has_perm(user, m, "create") for m in ("news", "announcement", "album")):
        panels.append(my_content_panel(user))
    return panels
