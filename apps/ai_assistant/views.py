"""Chức năng AI hỗ trợ. Tìm kiếm nội bộ không dùng AI nên vẫn hoạt động khi chưa cấu hình AI."""

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.views.decorators.http import require_POST

from apps.accounts.permissions import has_perm
from apps.core.audit import log_action
from apps.core.forms_base import BaseForm
from apps.core.permissions_mixins import require_perm

from . import service

LEGAL_WARNING = (
    "Nội dung do AI tạo ra chỉ là bản nháp tham khảo, có thể chứa sai sót. Người có thẩm quyền phải kiểm tra, "
    "chỉnh sửa và phê duyệt trước khi sử dụng. Mọi căn cứ pháp lý, số liệu phải được kiểm chứng với văn bản hiện hành."
)


class PostDraftForm(BaseForm):
    topic = forms.CharField(label="Chủ đề tin bài", max_length=255)
    points = forms.CharField(
        label="Ý chính / diễn biến (không ghi họ tên, thông tin của trẻ)", max_length=3000, widget=forms.Textarea(attrs={"rows": 5})
    )
    tone = forms.ChoiceField(label="Giọng văn", choices=[("trang-trong", "Trang trọng"), ("than-thien", "Thân thiện")])


class PlanDraftForm(BaseForm):
    level = forms.ChoiceField(
        label="Loại kế hoạch",
        choices=[
            ("chủ đề", "Kế hoạch chủ đề"),
            ("tuần", "Kế hoạch tuần"),
            ("hoạt động", "Kế hoạch hoạt động"),
            ("lớp", "Kế hoạch giáo dục lớp"),
            ("tổ chuyên môn", "Kế hoạch tổ chuyên môn"),
        ],
    )
    age_group = forms.ChoiceField(
        label="Độ tuổi", choices=[("nhà trẻ", "Nhà trẻ"), ("3-4 tuổi", "3-4 tuổi"), ("4-5 tuổi", "4-5 tuổi"), ("5-6 tuổi", "5-6 tuổi")]
    )
    theme = forms.CharField(label="Chủ đề / nội dung", max_length=255)
    duration = forms.CharField(label="Thời gian thực hiện", max_length=100, required=False)
    notes = forms.CharField(
        label="Yêu cầu thêm (mục tiêu, điều kiện lớp...)", max_length=3000, required=False, widget=forms.Textarea(attrs={"rows": 4})
    )


class SummarizeForm(BaseForm):
    text = forms.CharField(label="Dán nội dung cần tóm tắt", max_length=20000, required=False, widget=forms.Textarea(attrs={"rows": 8}))
    document_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("text") and not cleaned.get("document_id"):
            raise forms.ValidationError("Hãy dán nội dung hoặc chọn văn bản.")
        return cleaned


class EvidenceSuggestForm(BaseForm):
    description = forms.CharField(
        label="Mô tả hoạt động / tiêu chí cần minh chứng", max_length=3000, widget=forms.Textarea(attrs={"rows": 4})
    )


class ReportHelpForm(BaseForm):
    purpose = forms.CharField(
        label="Mục đích báo cáo",
        max_length=255,
        help_text="Ví dụ: Báo cáo sơ kết học kỳ I. Hệ thống chỉ gửi số liệu tổng hợp, không gửi dữ liệu cá nhân.",
    )


def _ai_guard(request):
    if not has_perm(request.user, "ai", "use"):
        raise PermissionDenied


def _render(request, template, ctx):
    ctx.setdefault("page_title", "AI hỗ trợ")
    ctx["ai_available"] = service.is_available()
    ctx["legal_warning"] = LEGAL_WARNING
    ctx["allow_internal"] = settings.AI_ALLOW_INTERNAL_DOCUMENTS
    return render(request, template, ctx)


def _run(request, feature, prompt):
    try:
        result = service.generate(prompt)
    except service.AIError as exc:
        messages.error(request, str(exc))
        return None
    log_action(request, f"ai:{feature}", None, module="ai", changes={"chars_in": len(prompt), "chars_out": len(result)})
    return result


@require_perm("ai", "use")
def index(request):
    return _render(request, "ai/index.html", {})


@require_perm("ai", "use")
def draft_post(request):
    if not has_perm(request.user, "news", "create"):
        raise PermissionDenied
    form = PostDraftForm(request.POST or None, user=request.user)
    result = None
    if request.method == "POST" and form.is_valid() and service.is_available():
        d = form.cleaned_data
        prompt = (
            f"Viết bản nháp tin bài cho website trường mầm non. Chủ đề: {d['topic']}.\n"
            f"Ý chính: {d['points']}\nGiọng văn: {d['tone']}.\n"
            "Trả về: dòng đầu là tiêu đề; sau đó 3-6 đoạn văn ngắn. Không dùng markdown, không nêu tên trẻ."
        )
        result = _run(request, "draft_post", prompt)
        if result:
            request.session["ai_last_post"] = {"topic": d["topic"], "text": result}
    return _render(request, "ai/draft_post.html", {"form": form, "result": result})


@require_perm("news", "create")
@require_POST
def save_post_draft(request):
    """Chuyển kết quả AI sang form tạo tin ở trạng thái Nháp (người dùng phải tự lưu và trình duyệt)."""
    _ai_guard(request)
    data = request.session.pop("ai_last_post", None)
    if not data:
        messages.error(request, "Không có bản nháp AI để sử dụng.")
        return redirect("ai:draft_post")
    lines = data["text"].strip().splitlines()
    title = lines[0].strip()[:255] if lines else data["topic"]
    body = "".join(f"<p>{escape(p.strip())}</p>" for p in lines[1:] if p.strip())
    request.session["ai_draft_post"] = {"title": title, "body": body}
    messages.info(request, "Đã chuyển bản nháp AI sang biểu mẫu. Hãy kiểm tra, chỉnh sửa trước khi lưu.")
    return redirect("content:news_create")


@require_perm("ai", "use")
def draft_plan(request):
    if not has_perm(request.user, "plan", "create"):
        raise PermissionDenied
    form = PlanDraftForm(request.POST or None, user=request.user)
    result = None
    if request.method == "POST" and form.is_valid() and service.is_available():
        d = form.cleaned_data
        prompt = (
            f"Soạn dự thảo {d['level']} cho trẻ {d['age_group']} với chủ đề: {d['theme']}. "
            f"Thời gian: {d['duration'] or 'chưa xác định'}.\nYêu cầu thêm: {d['notes']}\n"
            "Cấu trúc gợi ý: mục tiêu/yêu cầu cần đạt theo các lĩnh vực phát triển; nội dung; hoạt động; "
            "chuẩn bị môi trường, học liệu; đánh giá và điều chỉnh. Văn bản thuần, không markdown. "
            "Không khẳng định trích dẫn văn bản pháp lý cụ thể; nếu cần thì để [cần đối chiếu chương trình hiện hành]."
        )
        result = _run(request, "draft_plan", prompt)
        if result:
            request.session["ai_last_plan"] = {"title": f"Kế hoạch {d['level']}: {d['theme']}", "text": result}
    return _render(request, "ai/draft_plan.html", {"form": form, "result": result})


@require_perm("plan", "create")
@require_POST
def save_plan_draft(request):
    _ai_guard(request)
    data = request.session.pop("ai_last_plan", None)
    if not data:
        messages.error(request, "Không có bản nháp AI để sử dụng.")
        return redirect("ai:draft_plan")
    request.session["ai_draft_plan"] = {"title": data["title"][:255], "content": data["text"]}
    messages.info(request, "Đã chuyển dự thảo AI sang biểu mẫu kế hoạch (trạng thái Dự thảo).")
    return redirect("office:plan_create")


@require_perm("ai", "use")
def summarize(request):
    from apps.office.models import OfficialDocument

    doc = None
    doc_id = request.GET.get("van_ban") or request.POST.get("document_id")
    if doc_id and str(doc_id).isdigit():
        if not has_perm(request.user, "official_doc", "view"):
            raise PermissionDenied
        # Chỉ lấy văn bản người dùng được phép xem
        doc = get_object_or_404(OfficialDocument.objects.for_user(request.user), pk=doc_id)
    form = SummarizeForm(request.POST or None, user=request.user, initial={"document_id": doc.pk if doc else None})
    result = None
    if request.method == "POST" and form.is_valid() and service.is_available():
        if doc:
            if not settings.AI_ALLOW_INTERNAL_DOCUMENTS:
                messages.error(
                    request, "Hệ thống chưa cho phép gửi tài liệu nội bộ đến dịch vụ AI bên ngoài (AI_ALLOW_INTERNAL_DOCUMENTS=False)."
                )
                return _render(request, "ai/summarize.html", {"form": form, "doc": doc})
            if doc.access_level != "all":
                messages.error(request, "Văn bản có phạm vi truy cập hạn chế, không được gửi đến dịch vụ AI.")
                return _render(request, "ai/summarize.html", {"form": form, "doc": doc})
            text = f"Trích yếu: {doc.summary}\n\n{doc.content_text}"
        else:
            text = form.cleaned_data["text"]
        result = _run(
            request,
            "summarize",
            "Tóm tắt văn bản sau thành các ý chính, nêu rõ việc cần làm, thời hạn (nếu có) và đối tượng thực hiện:\n\n" + text,
        )
    return _render(request, "ai/summarize.html", {"form": form, "doc": doc, "result": result})


@require_perm("ai", "use")
def suggest_evidence(request):
    from apps.office.models import EvidenceCategory

    if not has_perm(request.user, "evidence", "view"):
        raise PermissionDenied
    form = EvidenceSuggestForm(request.POST or None, user=request.user)
    result = None
    if request.method == "POST" and form.is_valid() and service.is_available():
        cats = "\n".join(f"- {c.code}: {c.name}" for c in EvidenceCategory.objects.all()[:300])
        prompt = (
            f"Danh mục minh chứng hiện có:\n{cats or '(chưa có)'}\n\nMô tả: {form.cleaned_data['description']}\n"
            "Hãy gợi ý: (1) danh mục phù hợp nhất trong danh sách trên (ghi mã); (2) danh sách các loại minh chứng "
            "nên thu thập (văn bản, biên bản, hình ảnh hoạt động... ) và lưu ý bảo vệ hình ảnh, thông tin trẻ."
        )
        result = _run(request, "suggest_evidence", prompt)
    return _render(request, "ai/suggest_evidence.html", {"form": form, "result": result})


@require_perm("ai", "use")
def report_help(request):
    if not has_perm(request.user, "report", "view"):
        raise PermissionDenied
    from apps.reports.views import build_report

    form = ReportHelpForm(request.POST or None, user=request.user)
    result = None
    if request.method == "POST" and form.is_valid() and service.is_available():
        sections = build_report(request.user, {})
        stats = "\n".join(f"{t}: " + "; ".join(", ".join(str(c) for c in r) for r in rows) for t, _, rows in sections)
        prompt = (
            f"Lập dàn ý báo cáo '{form.cleaned_data['purpose']}' của trường mầm non dựa trên số liệu tổng hợp:\n"
            f"{stats}\nChỉ dùng số liệu đã cho; phần còn thiếu ghi [cần bổ sung]."
        )
        result = _run(request, "report_help", prompt)
    return _render(request, "ai/report_help.html", {"form": form, "result": result})


@login_required
def internal_search(request):
    """Tìm kiếm tài liệu nội bộ, lọc theo đúng quyền của người dùng (không gửi dữ liệu ra ngoài)."""
    from apps.office.models import EducationPlan, Evidence, OfficialDocument

    q = request.GET.get("q", "").strip()[:100]
    results = {}
    if len(q) >= 2:
        u = request.user
        if has_perm(u, "official_doc", "view"):
            results["docs"] = OfficialDocument.objects.for_user(u).filter(
                Q(number__icontains=q) | Q(symbol__icontains=q) | Q(summary__icontains=q) | Q(content_text__icontains=q)
            )[:20]
        if has_perm(u, "plan", "view"):
            results["plans"] = EducationPlan.objects.for_user(u).filter(Q(title__icontains=q) | Q(content__icontains=q))[:20]
        if has_perm(u, "evidence", "view"):
            results["evidence"] = Evidence.objects.for_user(u).filter(
                Q(code__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q)
            )[:20]
        log_action(request, "internal_search", None, module="ai", changes={"q": q})
    return _render(request, "ai/search.html", {"q": q, "results": results, "page_title": "Tìm kiếm tài liệu nội bộ"})
