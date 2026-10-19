"""Báo cáo, thống kê. Mỗi phần chỉ hiển thị khi người dùng có quyền xem chức năng tương ứng,
và dữ liệu được lọc theo phạm vi người dùng được phép xem."""

from datetime import datetime

from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404
from django.shortcuts import render

from apps.accounts.permissions import has_perm
from apps.core.audit import log_action
from apps.core.forms_base import BaseForm
from apps.core.permissions_mixins import require_perm
from apps.org.models import Campus, ProfessionalGroup

from . import exporters


class ReportFilterForm(BaseForm):
    date_from = forms.DateField(label="Từ ngày", required=False)
    date_to = forms.DateField(label="Đến ngày", required=False)
    group = forms.ModelChoiceField(label="Tổ chuyên môn", queryset=ProfessionalGroup.objects.all(), required=False)
    campus = forms.ModelChoiceField(label="Điểm trường", queryset=Campus.objects.all(), required=False)


def _range(qs, field, f):
    if f.get("date_from"):
        qs = qs.filter(**{f"{field}__date__gte" if field.endswith("_at") else f"{field}__gte": f["date_from"]})
    if f.get("date_to"):
        qs = qs.filter(**{f"{field}__date__lte" if field.endswith("_at") else f"{field}__lte": f["date_to"]})
    return qs


def _counts(qs, field, choices):
    data = dict(qs.values_list(field).annotate(n=Count("pk")).values_list(field, "n"))
    return [(label, data.get(key, 0)) for key, label in choices]


def build_report(user, f):
    """Trả về danh sách phần báo cáo: (tiêu đề, tiêu đề cột, các dòng)."""
    from apps.content.models import Album, Announcement, Disclosure, Post
    from apps.core.workflow import Status
    from apps.office.models import EducationPlan, Evidence, OfficialDocument, Task

    sections = []
    if has_perm(user, "news", "view"):
        rows = []
        for label, model, field in (
            ("Tin tức", Post, "created_at"),
            ("Thông báo", Announcement, "created_at"),
            ("Album", Album, "created_at"),
            ("Công khai giáo dục", Disclosure, "created_at"),
        ):
            qs = _range(model.objects.all(), field, f)
            c = dict(_counts(qs, "status", Status.choices))
            rows.append([label] + [c.get(lbl, 0) for _, lbl in Status.choices])
        sections.append(("Nội dung website", ["Loại"] + [lbl for _, lbl in Status.choices], rows))
    if has_perm(user, "task", "view"):
        qs = _range(Task.objects.for_user(user), "created_at", f)
        if f.get("group"):
            qs = qs.filter(assigned_group=f["group"])
        if f.get("campus"):
            qs = qs.filter(assigned_campus=f["campus"])
        rows = [[lbl, n] for lbl, n in _counts(qs, "status", Task.STATUSES)]
        rows.append(["Quá hạn (chưa hoàn thành)", qs.overdue().count()])
        rows.append(["Tổng", qs.count()])
        sections.append(("Tiến độ nhiệm vụ", ["Trạng thái", "Số lượng"], rows))
        by_group = (
            qs.exclude(assigned_group=None).values_list("assigned_group__name").annotate(total=Count("pk")).order_by("assigned_group__name")
        )
        if by_group:
            sections.append(("Nhiệm vụ theo tổ", ["Tổ", "Tổng số"], [list(r) for r in by_group]))
    if has_perm(user, "official_doc", "view"):
        qs = _range(OfficialDocument.objects.for_user(user), "issue_date", f)
        rows = []
        for key, lbl in OfficialDocument.DIRECTIONS:
            sub = qs.filter(direction=key)
            c = dict(_counts(sub, "processing_status", OfficialDocument.STATUSES))
            rows.append([lbl] + [c.get(s, 0) for _, s in OfficialDocument.STATUSES] + [sub.count()])
        sections.append(("Văn bản", ["Loại sổ"] + [s for _, s in OfficialDocument.STATUSES] + ["Tổng"], rows))
    if has_perm(user, "plan", "view"):
        qs = _range(EducationPlan.objects.for_user(user), "created_at", f)
        if f.get("group"):
            qs = qs.filter(group=f["group"])
        rows = []
        for key, lbl in EducationPlan.LEVELS:
            c = dict(_counts(qs.filter(level=key), "status", EducationPlan.STATUSES))
            rows.append([lbl] + [c.get(s, 0) for _, s in EducationPlan.STATUSES])
        sections.append(("Kế hoạch giáo dục", ["Cấp"] + [s for _, s in EducationPlan.STATUSES], rows))
    if has_perm(user, "evidence", "view"):
        qs = _range(Evidence.objects.for_user(user), "created_at", f)
        if f.get("group"):
            qs = qs.filter(group=f["group"])
        if f.get("campus"):
            qs = qs.filter(campus=f["campus"])
        rows = [list(r) for r in qs.values_list("category__code", "category__name").annotate(n=Count("pk")).order_by("category__code")]
        sections.append(("Minh chứng theo danh mục", ["Mã", "Danh mục", "Số minh chứng"], rows))
    return sections


@require_perm("report", "view")
def report_index(request):
    form = ReportFilterForm(request.GET or None, user=request.user)
    f = form.cleaned_data if form.is_valid() else {}
    sections = build_report(request.user, f)
    return render(
        request,
        "reports/index.html",
        {
            "form": form,
            "sections": sections,
            "page_title": "Báo cáo, thống kê",
            "can_export": has_perm(request.user, "report", "export"),
            "querystring": request.GET.urlencode(),
        },
    )


@require_perm("report", "export")
def report_export(request, fmt):
    form = ReportFilterForm(request.GET or None, user=request.user)
    f = form.cleaned_data if form.is_valid() else {}
    sections = build_report(request.user, f)
    title = "Báo cáo thống kê"
    if f.get("date_from") or f.get("date_to"):
        a = f.get("date_from").strftime("%d/%m/%Y") if f.get("date_from") else "…"
        b = f.get("date_to").strftime("%d/%m/%Y") if f.get("date_to") else "…"
        title += f" ({a} - {b})"
    log_action(request, f"export_{fmt}", None, module="report", changes={"filters": request.GET.dict()})
    if fmt == "pdf":
        return exporters.pdf_table_response("bao-cao-thong-ke", title, sections)
    if fmt == "xlsx":
        rows = []
        for sec_title, headers, data in sections:
            rows.append([sec_title.upper()])
            rows.append(headers)
            rows.extend(data)
            rows.append([])
        return exporters.excel_response("bao-cao-thong-ke", title, ["Báo cáo"], rows)
    raise Http404


@require_perm("audit", "export")
def audit_export(request):
    from apps.core.models import AuditLog

    qs = AuditLog.objects.select_related("user")
    df, dt_ = request.GET.get("date_from"), request.GET.get("date_to")
    try:
        if df:
            qs = qs.filter(created_at__date__gte=datetime.strptime(df, "%d/%m/%Y").date())
        if dt_:
            qs = qs.filter(created_at__date__lte=datetime.strptime(dt_, "%d/%m/%Y").date())
    except ValueError as exc:
        raise PermissionDenied("Ngày không hợp lệ") from exc
    rows = [[a.created_at, str(a.user or ""), a.action, a.module, a.object_repr, a.ip_address] for a in qs[:20000]]
    log_action(request, "export", None, module="audit", changes={"rows": len(rows)})
    return exporters.excel_response(
        "nhat-ky", "Nhật ký hệ thống", ["Thời điểm", "Người thực hiện", "Thao tác", "Chức năng", "Đối tượng", "IP"], rows
    )
