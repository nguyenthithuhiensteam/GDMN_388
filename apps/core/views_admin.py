"""Dashboard, cấu hình hệ thống, nhật ký, thông báo nội bộ, liên hệ."""
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import has_full_scope, has_perm

from .audit import diff_instances, log_action, snapshot
from .forms import AuditFilterForm, ContactStatusForm, SiteSettingsForm
from .models import AuditLog, ContactMessage, Notification, SiteSettings
from .permissions_mixins import require_perm


@login_required
def dashboard(request):
    from apps.accounts.models import User
    from apps.content.models import Album, Announcement, Disclosure, MediaItem, Post
    from apps.content.views_admin import scope_content
    from apps.office.models import EducationPlan, OfficialDocument, Task
    from apps.office.views import can_approve_plan

    from .workflow import Status

    user = request.user
    today = timezone.localdate()
    cards, alerts = [], []

    if has_perm(user, "user", "view"):
        cards.append(("Tài khoản đang hoạt động", User.objects.filter(is_active=True).count(), "users:user_list", "people"))
    if has_perm(user, "news", "view"):
        posts = scope_content(user, Post.objects.all())
        cards.append(("Tin đã xuất bản", posts.filter(status=Status.PUBLISHED).count(), "content:news_list", "newspaper"))
        cards.append(("Tin chờ duyệt", posts.filter(status=Status.PENDING).count(), "content:news_list", "hourglass"))
        if has_perm(user, "news", "approve"):
            n = Post.objects.filter(status=Status.PENDING).count()
            if n:
                alerts.append(("warning", f"{n} tin bài đang chờ duyệt.", "content:news_list"))
    if has_perm(user, "announcement", "view"):
        cards.append(("Thông báo đang hiển thị", Announcement.visible().count(), "content:announcement_list", "megaphone"))
        if has_perm(user, "announcement", "approve"):
            n = Announcement.objects.filter(status=Status.PENDING).count()
            if n:
                alerts.append(("warning", f"{n} thông báo đang chờ duyệt.", "content:announcement_list"))
    if has_perm(user, "album", "approve"):
        n = MediaItem.objects.filter(consent_status=MediaItem.CONSENT_PENDING).count()
        if n:
            alerts.append(("info", f"{n} ảnh/video chưa được kiểm tra quyền sử dụng hình ảnh.", "content:album_list"))
        n = Album.objects.filter(status=Status.PENDING).count()
        if n:
            alerts.append(("warning", f"{n} album đang chờ duyệt.", "content:album_list"))
    if has_perm(user, "disclosure", "view"):
        days = SiteSettings.load().disclosure_review_days
        due = Disclosure.objects.exclude(status=Status.ARCHIVED).filter(review_due__lte=today + timedelta(days=days))
        overdue = due.filter(review_due__lt=today).count()
        if overdue:
            alerts.append(("danger", f"{overdue} nội dung công khai đã quá hạn rà soát.", "content:disclosure_list"))
        if due.count() - overdue:
            alerts.append(("warning", f"{due.count() - overdue} nội dung công khai sắp đến hạn rà soát.", "content:disclosure_list"))
    recent_docs = []
    if has_perm(user, "official_doc", "view"):
        docs = OfficialDocument.objects.for_user(user)
        recent_docs = docs.order_by("-updated_at")[:5]
        n = docs.filter(responsible=user, processing_status__in=["new", "processing"], deadline__lt=today).count()
        if n:
            alerts.append(("danger", f"{n} văn bản bạn phụ trách đã quá hạn xử lý.", "office:doc_list"))
    upcoming_tasks = []
    if has_perm(user, "task", "view"):
        tasks = Task.objects.for_user(user)
        mine = tasks.filter(Q(assignee=user) | Q(assigned_group_id=user.group_id, assignee__isnull=True)) \
            if not has_full_scope(user) else tasks
        upcoming_tasks = mine.open().filter(due_date__isnull=False, due_date__lte=today + timedelta(days=7)) \
            .select_related("assignee").order_by("due_date")[:8]
        cards.append(("Nhiệm vụ đang mở", mine.open().count(), "office:task_list", "list-check"))
        overdue = mine.overdue().count()
        if overdue:
            alerts.append(("danger", f"{overdue} nhiệm vụ quá hạn.", "office:task_list"))
        if has_perm(user, "task", "approve"):
            waiting = tasks.filter(status="waiting", created_by=user).count()
            if waiting:
                alerts.append(("info", f"{waiting} nhiệm vụ bạn giao đang chờ xác nhận hoàn thành.", "office:task_list"))
    if has_perm(user, "plan", "approve"):
        pending = [p for p in EducationPlan.objects.filter(status="pending") if can_approve_plan(user, p)]
        if pending:
            alerts.append(("warning", f"{len(pending)} kế hoạch giáo dục chờ bạn duyệt.", "office:plan_list"))
    if has_perm(user, "contact", "view"):
        n = ContactMessage.objects.filter(status="new").count()
        if n:
            alerts.append(("info", f"{n} liên hệ mới từ phụ huynh/cộng đồng.", "core:contact_list"))

    activity = AuditLog.objects.select_related("user")
    if not has_perm(user, "audit", "view"):
        activity = activity.filter(user=user)
    return render(request, "core/dashboard.html", {
        "cards": cards, "alerts": alerts, "recent_docs": recent_docs, "upcoming_tasks": upcoming_tasks,
        "activity": activity[:10], "notifications": Notification.objects.filter(user=user, is_read=False)[:5],
        "page_title": "Tổng quan", "ai_enabled": settings.AI_ENABLED,
    })


@require_perm("settings", "view")
def site_settings(request):
    obj, _ = SiteSettings.objects.get_or_create(pk=1)
    can_edit = has_perm(request.user, "settings", "edit")
    before = snapshot(obj)
    form = SiteSettingsForm(request.POST or None, request.FILES or None, instance=obj, user=request.user)
    if request.method == "POST":
        if not can_edit:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if form.is_valid():
            obj = form.save()
            from .images import optimize_image_field

            for f in ("logo", "banner"):
                if f in form.changed_data and getattr(obj, f):
                    optimize_image_field(getattr(obj, f), max_dim=600 if f == "logo" else 1920)
            obj.save()
            log_action(request, "settings_update", obj, module="settings", changes=diff_instances(before, snapshot(obj)))
            messages.success(request, "Đã lưu cấu hình.")
            return redirect("core:settings")
        messages.error(request, "Vui lòng kiểm tra lại các trường được đánh dấu.")
    from apps.org.models import SchoolYear

    system_info = {
        "env": settings.DJANGO_ENV,
        "debug": settings.DEBUG,
        "database": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
        "email_backend": settings.EMAIL_BACKEND.rsplit(".", 1)[-1],
        "email_notifications": settings.EMAIL_NOTIFICATIONS_ENABLED,
        "media_root": settings.MEDIA_ROOT,
        "protected_root": settings.PROTECTED_MEDIA_ROOT,
        "backup_dir": settings.BACKUP_DIR,
        "backup_keep": settings.BACKUP_KEEP,
        "max_upload": settings.MAX_UPLOAD_MB,
        "ai_enabled": settings.AI_ENABLED,
        "ai_configured": bool(settings.AI_API_KEY),
        "ai_internal": settings.AI_ALLOW_INTERNAL_DOCUMENTS,
        "current_year": SchoolYear.current(),
    }
    backups = []
    if settings.BACKUP_DIR.exists():
        backups = sorted(settings.BACKUP_DIR.glob("backup-*.zip"), reverse=True)[:10]
        backups = [{"name": b.name, "size": b.stat().st_size, "mtime": datetime.fromtimestamp(b.stat().st_mtime)}
                   for b in backups]
    return render(request, "core/settings.html", {
        "form": form, "can_edit": can_edit, "system": system_info, "backups": backups, "page_title": "Cấu hình hệ thống",
    })


@require_perm("audit", "view")
def audit_list(request):
    form = AuditFilterForm(request.GET or None, user=request.user)
    qs = AuditLog.objects.select_related("user")
    if form.is_valid():
        q = form.cleaned_data.get("q")
        if q:
            qs = qs.filter(Q(action__icontains=q) | Q(object_repr__icontains=q) | Q(user__username__icontains=q)
                           | Q(user__full_name__icontains=q) | Q(module__icontains=q))
        if form.cleaned_data.get("date_from"):
            qs = qs.filter(created_at__date__gte=form.cleaned_data["date_from"])
        if form.cleaned_data.get("date_to"):
            qs = qs.filter(created_at__date__lte=form.cleaned_data["date_to"])
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "core/audit_list.html", {
        "form": form, "page_obj": Paginator(qs, 50).get_page(request.GET.get("page")),
        "page_title": "Nhật ký hệ thống", "querystring": params.urlencode(),
        "can_export": has_perm(request.user, "audit", "export"),
    })


@login_required
def notifications(request):
    qs = Notification.objects.filter(user=request.user)
    return render(request, "core/notifications.html", {
        "page_obj": Paginator(qs, 30).get_page(request.GET.get("page")), "page_title": "Nhắc việc",
    })


@login_required
@require_POST
def notification_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    from django.utils.http import url_has_allowed_host_and_scheme

    if n.url and url_has_allowed_host_and_scheme(n.url, allowed_hosts={request.get_host()}):
        return redirect(n.url)
    return redirect("core:notifications")


@login_required
@require_POST
def notification_read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "Đã đánh dấu tất cả là đã đọc.")
    return redirect("core:notifications")


@require_perm("contact", "view")
def contact_list(request):
    qs = ContactMessage.objects.all()
    status = request.GET.get("status")
    if status in dict(ContactMessage.STATUS):
        qs = qs.filter(status=status)
    return render(request, "core/contact_list.html", {
        "page_obj": Paginator(qs, 30).get_page(request.GET.get("page")), "status": status,
        "statuses": ContactMessage.STATUS, "page_title": "Liên hệ",
    })


@require_perm("contact", "view")
def contact_detail(request, pk):
    obj = get_object_or_404(ContactMessage, pk=pk)
    form = ContactStatusForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "contact_update", obj, module="contact")
        messages.success(request, "Đã cập nhật.")
        return redirect("core:contact_list")
    return render(request, "core/contact_detail.html", {
        "obj": obj, "form": form, "page_title": "Liên hệ", "can_delete": has_perm(request.user, "contact", "delete"),
    })


@require_perm("contact", "delete")
@require_POST
def contact_delete(request, pk):
    obj = get_object_or_404(ContactMessage, pk=pk)
    log_action(request, "delete", obj, module="contact")
    obj.delete()
    messages.success(request, "Đã xóa liên hệ.")
    return redirect("core:contact_list")
