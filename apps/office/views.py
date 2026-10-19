"""View quản lý văn bản, kế hoạch giáo dục, nhiệm vụ và minh chứng."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import ROLE_GROUP_LEADER, has_full_scope, has_perm, is_manager
from apps.core.audit import log_action
from apps.core.crud import AdminCreateView, AdminDeleteView, AdminDetailView, AdminListView, AdminUpdateView
from apps.core.downloads import serve_protected
from apps.core.models import AuditLog
from apps.core.notify import notify
from apps.core.permissions_mixins import require_perm
from apps.reports import exporters

from . import forms
from .models import (
    EducationPlan,
    Evidence,
    EvidenceCategory,
    EvidenceFile,
    OfficialDocument,
    PlanComment,
    PlanExportTemplate,
    PlanVersion,
    Task,
    TaskAttachment,
    TaskComment,
)


def _history(obj):
    return AuditLog.objects.filter(object_type=obj._meta.label, object_id=str(obj.pk)).select_related("user")[:50]


# ============================================================================
# VĂN BẢN
# ============================================================================
class DocScope:
    def get_queryset(self):
        return OfficialDocument.objects.for_user(self.request.user).select_related("doc_type", "issuer", "responsible")


class DocList(AdminListView):
    model = OfficialDocument
    module = "official_doc"
    page_title = "Quản lý văn bản"
    url_prefix = "office:doc"
    template_name = "office/doc_list.html"
    columns = [
        ("number", "Số"),
        ("symbol", "Ký hiệu"),
        ("issue_date", "Ngày ban hành"),
        ("summary", "Trích yếu"),
        ("doc_type", "Loại"),
        ("processing_status", "Trạng thái"),
        ("deadline", "Hạn xử lý"),
    ]
    search_fields = ["number", "symbol", "summary", "content_text", "issuer_text"]
    filter_fields = ["direction", "doc_type", "field", "processing_status"]
    has_detail = True

    def scope_queryset(self, qs):
        return qs.for_user(self.request.user).select_related("doc_type", "issuer", "responsible")

    def get_queryset(self):
        qs = super().get_queryset()
        for key, lookup in (("tu_ngay", "issue_date__gte"), ("den_ngay", "issue_date__lte")):
            val = self.request.GET.get(key)
            if val:
                from datetime import datetime

                try:
                    qs = qs.filter(**{lookup: datetime.strptime(val, "%d/%m/%Y").date()})
                except ValueError:
                    messages.warning(self.request, "Ngày lọc không hợp lệ (định dạng dd/mm/yyyy).")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tu_ngay"] = self.request.GET.get("tu_ngay", "")
        ctx["den_ngay"] = self.request.GET.get("den_ngay", "")
        ctx["can_export"] = has_perm(self.request.user, "official_doc", "export")
        return ctx


class _DocEdit(DocScope):
    model = OfficialDocument
    form_class = forms.OfficialDocumentForm
    module = "official_doc"
    url_prefix = "office:doc"
    page_title = "Văn bản"

    def can_modify(self, obj):
        user = self.request.user
        return has_full_scope(user) or obj.created_by_id == user.pk or obj.responsible_id == user.pk

    def get_success_url(self):
        return reverse("office:doc_detail", kwargs={"pk": self.object.pk})

    def after_save(self, form, obj, created):
        if obj.responsible and (created or "responsible" in form.changed_data) and obj.responsible != self.request.user:
            notify([obj.responsible], f"Bạn được giao xử lý văn bản: {obj}", reverse("office:doc_detail", args=[obj.pk]), email=True)


class DocCreate(_DocEdit, AdminCreateView):
    pass


class DocUpdate(_DocEdit, AdminUpdateView):
    pass


class DocDelete(_DocEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("office:doc_list")


class DocDetail(_DocEdit, AdminDetailView):
    template_name = "office/doc_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["history"] = _history(self.object)
        ctx["can_modify"] = self.can_modify(self.object) and has_perm(self.request.user, "official_doc", "edit")
        ctx["can_download"] = has_perm(self.request.user, "official_doc", "download")
        return ctx


@require_perm("official_doc", "download")
def doc_download(request, pk):
    doc = get_object_or_404(OfficialDocument.objects.for_user(request.user), pk=pk)
    log_action(request, "download", doc, module="official_doc")
    return serve_protected(doc.file, f"{doc.number}-{doc.symbol}".strip("-").replace("/", "-"))


@require_perm("official_doc", "export")
def doc_export(request):
    view = DocList()
    view.setup(request)
    qs = view.get_queryset()
    rows = [
        [
            d.get_direction_display(),
            d.number,
            d.symbol,
            d.issue_date,
            d.issuer_name,
            str(d.doc_type or ""),
            str(d.field or ""),
            d.summary,
            str(d.responsible or ""),
            d.get_processing_status_display(),
            d.deadline,
        ]
        for d in qs
    ]
    log_action(request, "export", None, module="official_doc", changes={"rows": len(rows), "query": request.GET.dict()})
    return exporters.excel_response(
        "danh-sach-van-ban",
        "Danh sách văn bản",
        [
            "Loại sổ",
            "Số",
            "Ký hiệu",
            "Ngày ban hành",
            "Cơ quan ban hành",
            "Loại",
            "Lĩnh vực",
            "Trích yếu",
            "Người phụ trách",
            "Trạng thái",
            "Hạn xử lý",
        ],
        rows,
    )


# ============================================================================
# KẾ HOẠCH GIÁO DỤC
# ============================================================================
def can_approve_plan(user, plan):
    if not has_perm(user, "plan", "approve"):
        return False
    if is_manager(user):
        return True
    if plan.level == "school":
        return False
    return user.role == ROLE_GROUP_LEADER and plan.group_id and plan.group_id == user.group_id


def can_edit_plan(user, plan):
    return (
        has_perm(user, "plan", "edit")
        and plan.is_editable
        and (
            plan.created_by_id == user.pk
            or has_full_scope(user)
            or (user.role == ROLE_GROUP_LEADER and plan.group_id and plan.group_id == user.group_id)
        )
    )


PLAN_TRANSITIONS = {
    # tên: (nhãn, từ trạng thái, đến trạng thái, kiểu kiểm tra)
    "consult": ("Gửi lấy góp ý", {"draft"}, "consulting", "owner"),
    "submit": ("Trình duyệt", {"draft", "consulting"}, "pending", "owner"),
    "approve": ("Phê duyệt", {"pending"}, "approved", "approver"),
    "return": ("Trả lại chỉnh sửa", {"pending", "approved"}, "draft", "approver"),
    "official": ("Ban hành chính thức", {"approved"}, "official", "approver"),
    "archive": ("Lưu trữ", {"official", "approved"}, "archived", "approver"),
}


def plan_transitions_for(user, plan):
    result = []
    for name, (label, sources, _, check) in PLAN_TRANSITIONS.items():
        if plan.status not in sources:
            continue
        ok = can_edit_plan(user, plan) if check == "owner" else can_approve_plan(user, plan)
        if ok:
            result.append({"name": name, "label": label})
    return result


def _snapshot_plan(plan, user, note=""):
    last = plan.versions.aggregate(m=Max("version_no"))["m"] or 0
    return PlanVersion.objects.create(
        plan=plan,
        version_no=last + 1,
        title=plan.title,
        content=plan.content,
        file=plan.file.name if plan.file else "",
        status=plan.status,
        note=note,
        created_by=user,
    )


class PlanScope:
    def get_queryset(self):
        return EducationPlan.objects.for_user(self.request.user).select_related("school_year", "group", "school_class", "created_by")


class PlanList(AdminListView):
    model = EducationPlan
    module = "plan"
    page_title = "Kế hoạch giáo dục"
    url_prefix = "office:plan"
    columns = [
        ("title", "Tên kế hoạch"),
        ("level", "Cấp"),
        ("school_year", "Năm học"),
        ("group", "Tổ"),
        ("school_class", "Lớp"),
        ("status", "Trạng thái"),
        ("updated_at", "Cập nhật"),
    ]
    search_fields = ["title", "content"]
    filter_fields = ["level", "status", "school_year", "group"]
    has_detail = True

    def scope_queryset(self, qs):
        return qs.for_user(self.request.user).select_related("school_year", "group", "school_class")


class _PlanEdit(PlanScope):
    model = EducationPlan
    form_class = forms.EducationPlanForm
    module = "plan"
    url_prefix = "office:plan"
    page_title = "Kế hoạch giáo dục"

    def can_modify(self, obj):
        return can_edit_plan(self.request.user, obj)

    def get_success_url(self):
        return reverse("office:plan_detail", kwargs={"pk": self.object.pk})

    def after_save(self, form, obj, created):
        _snapshot_plan(obj, self.request.user, form.cleaned_data.get("version_note", "") or ("Tạo mới" if created else ""))


class PlanCreate(_PlanEdit, AdminCreateView):
    def get_initial(self):
        initial = super().get_initial()
        from apps.org.models import SchoolYear

        initial["school_year"] = SchoolYear.current()
        draft = self.request.session.pop("ai_draft_plan", None)
        if draft:
            initial.update(title=draft.get("title", ""), content=draft.get("content", ""))
        return initial


class PlanUpdate(_PlanEdit, AdminUpdateView):
    pass


class PlanDelete(_PlanEdit, AdminDeleteView):
    def can_modify(self, obj):
        return obj.status == "draft" and (obj.created_by_id == self.request.user.pk or has_full_scope(self.request.user))

    def get_success_url(self):
        return reverse("office:plan_list")


class PlanDetail(_PlanEdit, AdminDetailView):
    template_name = "office/plan_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        plan, user = self.object, self.request.user
        ctx.update(
            transitions=plan_transitions_for(user, plan),
            versions=plan.versions.select_related("created_by"),
            comments=plan.comments.select_related("user"),
            comment_form=forms.PlanCommentForm(user=user),
            can_modify=can_edit_plan(user, plan),
            can_download=has_perm(user, "plan", "download"),
            templates=PlanExportTemplate.objects.all(),
            history=_history(plan),
            children=EducationPlan.objects.for_user(user).filter(parent=plan),
        )
        return ctx


@require_perm("plan", "view")
@require_POST
def plan_transition(request, pk, name):
    plan = get_object_or_404(EducationPlan.objects.for_user(request.user), pk=pk)
    if name not in {t["name"] for t in plan_transitions_for(request.user, plan)}:
        raise PermissionDenied
    _, _, target, _ = PLAN_TRANSITIONS[name]
    old = plan.status
    plan.status = target
    plan.updated_by = request.user
    if name == "approve":
        plan.approved_by, plan.approved_at = request.user, timezone.now()
    if name == "official":
        plan.official_at = timezone.now()
    if name == "return":
        plan.approved_by = plan.approved_at = None
    plan.save()
    note = request.POST.get("note", "").strip()[:255]
    _snapshot_plan(plan, request.user, f"{PLAN_TRANSITIONS[name][0]}. {note}".strip())
    log_action(request, f"plan:{name}", plan, module="plan", changes={"status": [old, target], "note": note})
    if plan.created_by and plan.created_by != request.user:
        notify(
            [plan.created_by], f"Kế hoạch '{plan}' chuyển sang: {plan.get_status_display()}", reverse("office:plan_detail", args=[plan.pk])
        )
    messages.success(request, f"Kế hoạch đã chuyển sang trạng thái: {plan.get_status_display()}.")
    return redirect("office:plan_detail", pk=plan.pk)


@require_perm("plan", "view")
@require_POST
def plan_comment(request, pk):
    plan = get_object_or_404(EducationPlan.objects.for_user(request.user), pk=pk)
    form = forms.PlanCommentForm(request.POST, user=request.user)
    if form.is_valid():
        last = plan.latest_version
        PlanComment.objects.create(
            plan=plan, user=request.user, content=form.cleaned_data["content"], version_no=last.version_no if last else 0
        )
        if plan.created_by and plan.created_by != request.user:
            notify([plan.created_by], f"Có góp ý mới cho kế hoạch '{plan}'", reverse("office:plan_detail", args=[plan.pk]))
        messages.success(request, "Đã gửi góp ý.")
    return redirect("office:plan_detail", pk=plan.pk)


@require_perm("plan", "download")
def plan_download(request, pk, version=None):
    plan = get_object_or_404(EducationPlan.objects.for_user(request.user), pk=pk)
    if version:
        v = get_object_or_404(PlanVersion, plan=plan, version_no=version)
        return serve_protected(v.file, f"{plan.title}-v{version}")
    return serve_protected(plan.file, plan.title)


@require_perm("plan", "download")
def plan_export(request, pk, fmt):
    plan = get_object_or_404(EducationPlan.objects.for_user(request.user), pk=pk)
    tpl_id = request.GET.get("mau")
    template = (
        PlanExportTemplate.objects.filter(pk=tpl_id).first() if tpl_id and tpl_id.isdigit() else None
    ) or PlanExportTemplate.objects.filter(is_default=True).first()
    log_action(request, f"export_{fmt}", plan, module="plan")
    if fmt == "docx":
        return exporters.plan_docx_response(plan, template)
    if fmt == "pdf":
        return exporters.plan_pdf_response(plan, template)
    raise Http404


class TemplateList(AdminListView):
    model = PlanExportTemplate
    module = "plan"
    action = "approve"
    page_title = "Mẫu xuất kế hoạch"
    url_prefix = "office:template"
    columns = [("name", "Tên mẫu"), ("title_prefix", "Tiền tố"), ("signature_title", "Chức danh ký"), ("is_default", "Mặc định")]


class _TemplateEdit:
    model = PlanExportTemplate
    form_class = forms.PlanExportTemplateForm
    module = "plan"
    action = "approve"
    url_prefix = "office:template"
    page_title = "Mẫu xuất kế hoạch"

    def can_modify(self, obj):
        return is_manager(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        # Mẫu xuất dùng chung toàn trường: chỉ lãnh đạo được tạo/sửa/xóa.
        if request.user.is_authenticated and not is_manager(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class TemplateCreate(_TemplateEdit, AdminCreateView):
    action = "approve"


class TemplateUpdate(_TemplateEdit, AdminUpdateView):
    action = "approve"


class TemplateDelete(_TemplateEdit, AdminDeleteView):
    action = "approve"


# ============================================================================
# NHIỆM VỤ
# ============================================================================
def can_confirm_task(user, task):
    if not has_perm(user, "task", "approve"):
        return False
    if task.created_by_id == user.pk or is_manager(user):
        return True
    return user.role == ROLE_GROUP_LEADER and task.assigned_group_id and task.assigned_group_id == user.group_id


def is_task_worker(user, task):
    if task.assignee_id:
        return task.assignee_id == user.pk
    if task.assigned_group_id:
        return task.assigned_group_id == user.group_id
    return bool(task.assigned_campus_id and task.assigned_campus_id == user.campus_id)


def task_status_choices(user, task):
    choices = []
    labels = dict(Task.STATUSES)
    if is_task_worker(user, task) and has_perm(user, "task", "edit"):
        flow = {"todo": ["in_progress", "waiting"], "in_progress": ["waiting", "todo"], "waiting": ["in_progress"]}
        choices += flow.get(task.status, [])
    if can_confirm_task(user, task):
        if task.status == "waiting":
            choices += ["done", "in_progress"]
        elif task.status == "done":
            choices += ["in_progress"]
        elif task.status in ("todo", "in_progress"):
            choices += ["done"]
    seen, result = set(), []
    for c in choices:
        if c not in seen and c != task.status:
            seen.add(c)
            result.append((c, labels[c]))
    return result


class TaskScope:
    def get_queryset(self):
        return Task.objects.for_user(self.request.user).select_related("assignee", "assigned_group", "assigned_campus", "created_by")


class TaskList(AdminListView):
    model = Task
    module = "task"
    page_title = "Nhiệm vụ"
    url_prefix = "office:task"
    template_name = "office/task_list.html"
    columns = [
        ("title", "Nhiệm vụ"),
        ("target_label", "Giao cho"),
        ("due_date", "Thời hạn"),
        ("priority", "Ưu tiên"),
        ("status", "Trạng thái"),
        ("created_by", "Người giao"),
    ]
    search_fields = ["title", "description"]
    filter_fields = ["status", "priority", "assigned_group", "assigned_campus"]
    has_detail = True

    def scope_queryset(self, qs):
        return qs.for_user(self.request.user).select_related("assignee", "assigned_group", "assigned_campus", "created_by")

    def get_queryset(self):
        qs = super().get_queryset()
        view = self.request.GET.get("xem")
        if view == "cua-toi":
            qs = qs.filter(assignee=self.request.user)
        elif view == "toi-giao":
            qs = qs.filter(created_by=self.request.user)
        elif view == "qua-han":
            qs = qs.overdue()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = Task.objects.for_user(self.request.user)
        ctx["xem"] = self.request.GET.get("xem", "")
        ctx["progress"] = {
            "total": base.count(),
            "done": base.filter(status="done").count(),
            "waiting": base.filter(status="waiting").count(),
            "overdue": base.overdue().count(),
        }
        ctx["can_export"] = has_perm(self.request.user, "task", "export")
        return ctx


class _TaskEdit(TaskScope):
    model = Task
    form_class = forms.TaskForm
    module = "task"
    url_prefix = "office:task"
    page_title = "Nhiệm vụ"

    def can_modify(self, obj):
        user = self.request.user
        return obj.created_by_id == user.pk or is_manager(user)

    def get_success_url(self):
        return reverse("office:task_detail", kwargs={"pk": self.object.pk})

    def after_save(self, form, obj, created):
        changed = created or {"assignee", "assigned_group", "assigned_campus"} & set(form.changed_data)
        if not changed:
            return
        from apps.accounts.models import User

        if obj.assignee:
            targets = [obj.assignee]
        elif obj.assigned_group:
            targets = list(User.objects.filter(group=obj.assigned_group, is_active=True))
        else:
            targets = list(User.objects.filter(campus=obj.assigned_campus, is_active=True))
        targets = [u for u in targets if u != self.request.user]
        due = f" (hạn {obj.due_date:%d/%m/%Y})" if obj.due_date else ""
        notify(targets, f"Nhiệm vụ mới: {obj.title}{due}", reverse("office:task_detail", args=[obj.pk]), email=True)


class TaskCreate(_TaskEdit, AdminCreateView):
    pass


class TaskUpdate(_TaskEdit, AdminUpdateView):
    pass


class TaskDelete(_TaskEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("office:task_list")


class TaskDetail(_TaskEdit, AdminDetailView):
    template_name = "office/task_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        task, user = self.object, self.request.user
        choices = task_status_choices(user, task)
        ctx.update(
            status_form=forms.TaskStatusForm(choices=choices, user=user) if choices else None,
            comment_form=forms.CommentForm(user=user),
            attach_form=forms.AttachmentForm(user=user),
            can_attach=has_perm(user, "task", "edit") and (is_task_worker(user, task) or self.can_modify(task)),
            can_modify=self.can_modify(task) and has_perm(user, "task", "edit"),
            comments=task.comments.select_related("user"),
            attachments=task.attachments.select_related("uploaded_by"),
        )
        return ctx


def _task_for(request, pk):
    return get_object_or_404(Task.objects.for_user(request.user), pk=pk)


@require_perm("task", "view")
@require_POST
def task_status(request, pk):
    task = _task_for(request, pk)
    choices = task_status_choices(request.user, task)
    form = forms.TaskStatusForm(request.POST, choices=choices, user=request.user)
    if not choices or not form.is_valid():
        raise PermissionDenied
    old, new = task.status, form.cleaned_data["status"]
    task.status = new
    task.updated_by = request.user
    if new == "done":
        task.completed_at, task.confirmed_by = timezone.now(), request.user
    else:
        task.completed_at = task.confirmed_by = None
    task.save()
    labels = dict(Task.STATUSES)
    text = f"Chuyển trạng thái: {labels[old]} → {labels[new]}"
    if form.cleaned_data["note"]:
        text += f". {form.cleaned_data['note']}"
    TaskComment.objects.create(task=task, user=request.user, content=text, is_system=True)
    log_action(request, "task_status", task, module="task", changes={"status": [old, new]})
    recipients = {task.created_by, task.assignee} - {request.user, None}
    notify(list(recipients), f"Nhiệm vụ '{task.title}': {labels[new]}", reverse("office:task_detail", args=[task.pk]))
    messages.success(request, "Đã cập nhật trạng thái.")
    return redirect("office:task_detail", pk=task.pk)


@require_perm("task", "view")
@require_POST
def task_comment(request, pk):
    task = _task_for(request, pk)
    form = forms.CommentForm(request.POST, user=request.user)
    if form.is_valid():
        TaskComment.objects.create(task=task, user=request.user, content=form.cleaned_data["content"])
        recipients = {task.created_by, task.assignee} - {request.user, None}
        notify(list(recipients), f"Phản hồi mới: {task.title}", reverse("office:task_detail", args=[task.pk]))
        messages.success(request, "Đã gửi nhận xét.")
    return redirect("office:task_detail", pk=task.pk)


@require_perm("task", "edit")
@require_POST
def task_attach(request, pk):
    task = _task_for(request, pk)
    if not (is_task_worker(request.user, task) or task.created_by_id == request.user.pk or is_manager(request.user)):
        raise PermissionDenied
    form = forms.AttachmentForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        f = form.cleaned_data["file"]
        att = TaskAttachment(task=task, description=form.cleaned_data["description"], uploaded_by=request.user, original_name=f.name[:255])
        att.file.save(f.name, f, save=True)
        log_action(request, "task_attach", task, module="task", changes={"file": att.original_name})
        messages.success(request, "Đã tải lên minh chứng.")
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect("office:task_detail", pk=task.pk)


@require_perm("task", "view")
def task_attachment_download(request, pk):
    att = get_object_or_404(TaskAttachment.objects.select_related("task"), pk=pk)
    if not Task.objects.for_user(request.user).filter(pk=att.task_id).exists():
        raise PermissionDenied
    return serve_protected(att.file, att.original_name.rsplit(".", 1)[0] if att.original_name else None)


@require_perm("task", "export")
def task_export(request):
    view = TaskList()
    view.setup(request)
    qs = view.get_queryset()
    rows = [
        [t.title, t.target_label, t.due_date, t.get_priority_display(), t.display_status, str(t.created_by or ""), t.completed_at]
        for t in qs
    ]
    log_action(request, "export", None, module="task", changes={"rows": len(rows)})
    return exporters.excel_response(
        "nhiem-vu",
        "Danh sách nhiệm vụ",
        ["Nhiệm vụ", "Giao cho", "Thời hạn", "Ưu tiên", "Trạng thái", "Người giao", "Hoàn thành lúc"],
        rows,
    )


# ============================================================================
# MINH CHỨNG
# ============================================================================
class EvidenceCategoryList(AdminListView):
    model = EvidenceCategory
    module = "evidence"
    page_title = "Danh mục minh chứng"
    url_prefix = "office:evcat"
    columns = [("code", "Mã"), ("name", "Tên"), ("parent", "Thuộc"), ("order", "Thứ tự")]
    search_fields = ["code", "name"]


class _EvCatEdit:
    model = EvidenceCategory
    form_class = forms.EvidenceCategoryForm
    module = "evidence"
    url_prefix = "office:evcat"
    page_title = "Danh mục minh chứng"

    def can_modify(self, obj):
        return has_full_scope(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_full_scope(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class EvidenceCategoryCreate(_EvCatEdit, AdminCreateView):
    pass


class EvidenceCategoryUpdate(_EvCatEdit, AdminUpdateView):
    pass


class EvidenceCategoryDelete(_EvCatEdit, AdminDeleteView):
    pass


class EvidenceScope:
    def get_queryset(self):
        return Evidence.objects.for_user(self.request.user).select_related("category", "responsible", "group", "campus")


class EvidenceList(AdminListView):
    model = Evidence
    module = "evidence"
    page_title = "Minh chứng"
    url_prefix = "office:evidence"
    template_name = "office/evidence_list.html"
    columns = [
        ("code", "Mã"),
        ("title", "Tên minh chứng"),
        ("category", "Danh mục"),
        ("evidence_date", "Ngày"),
        ("responsible", "Phụ trách"),
        ("group", "Tổ"),
    ]
    search_fields = ["code", "title", "description", "criterion", "source"]
    filter_fields = ["category", "school_year", "group", "campus"]
    has_detail = True

    def scope_queryset(self, qs):
        return qs.for_user(self.request.user).select_related("category", "responsible", "group", "campus")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_export"] = has_perm(self.request.user, "evidence", "export")
        return ctx


class _EvidenceEdit(EvidenceScope):
    model = Evidence
    form_class = forms.EvidenceForm
    module = "evidence"
    url_prefix = "office:evidence"
    page_title = "Minh chứng"

    def can_modify(self, obj):
        user = self.request.user
        return has_full_scope(user) or obj.created_by_id == user.pk or obj.responsible_id == user.pk

    def get_success_url(self):
        return reverse("office:evidence_detail", kwargs={"pk": self.object.pk})

    def after_save(self, form, obj, created):
        f = form.cleaned_data.get("upload")
        if f:
            _add_evidence_file(obj, f, form.cleaned_data.get("upload_note", ""), self.request.user)


def _add_evidence_file(evidence, f, note, user):
    with transaction.atomic():
        last = EvidenceFile.objects.select_for_update().filter(evidence=evidence).aggregate(m=Max("version_no"))["m"] or 0
        ef = EvidenceFile(evidence=evidence, version_no=last + 1, note=note, uploaded_by=user, original_name=f.name[:255])
        ef.file.save(f.name, f, save=True)
    return ef


class EvidenceCreate(_EvidenceEdit, AdminCreateView):
    pass


class EvidenceUpdate(_EvidenceEdit, AdminUpdateView):
    pass


class EvidenceDelete(_EvidenceEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("office:evidence_list")


class EvidenceDetail(_EvidenceEdit, AdminDetailView):
    template_name = "office/evidence_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            files=self.object.files.select_related("uploaded_by"),
            file_form=forms.EvidenceFileForm(user=self.request.user),
            can_modify=self.can_modify(self.object) and has_perm(self.request.user, "evidence", "edit"),
            can_download=has_perm(self.request.user, "evidence", "download"),
            history=_history(self.object),
        )
        return ctx


@require_perm("evidence", "edit")
@require_POST
def evidence_upload(request, pk):
    ev = get_object_or_404(Evidence.objects.for_user(request.user), pk=pk)
    if not (has_full_scope(request.user) or ev.created_by_id == request.user.pk or ev.responsible_id == request.user.pk):
        raise PermissionDenied
    form = forms.EvidenceFileForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        ef = _add_evidence_file(ev, form.cleaned_data["file"], form.cleaned_data["note"], request.user)
        log_action(request, "evidence_upload", ev, module="evidence", changes={"version": ef.version_no})
        messages.success(request, f"Đã tải lên phiên bản {ef.version_no}.")
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect("office:evidence_detail", pk=ev.pk)


@require_perm("evidence", "download")
def evidence_download(request, pk, version):
    ev = get_object_or_404(Evidence.objects.for_user(request.user), pk=pk)
    ef = get_object_or_404(EvidenceFile, evidence=ev, version_no=version)
    log_action(request, "download", ev, module="evidence", changes={"version": version})
    return serve_protected(ef.file, f"{ev.code}-v{version}")


@require_perm("evidence", "export")
def evidence_export(request):
    view = EvidenceList()
    view.setup(request)
    qs = view.get_queryset()
    rows = []
    for e in qs.prefetch_related("files"):
        current = e.current_file
        rows.append(
            [
                e.code,
                e.title,
                str(e.category),
                e.criterion,
                e.source,
                e.evidence_date,
                str(e.responsible or ""),
                str(e.group or ""),
                str(e.campus or ""),
                str(e.plan or ""),
                str(e.task or ""),
                e.report_ref,
                current.version_no if current else 0,
            ]
        )
    log_action(request, "export", None, module="evidence", changes={"rows": len(rows)})
    return exporters.excel_response(
        "danh-muc-minh-chung",
        "Danh mục minh chứng",
        [
            "Mã",
            "Tên minh chứng",
            "Danh mục",
            "Tiêu chí",
            "Nguồn",
            "Ngày",
            "Phụ trách",
            "Tổ",
            "Điểm trường",
            "Kế hoạch",
            "Nhiệm vụ",
            "Báo cáo",
            "Số phiên bản tệp",
        ],
        rows,
    )
