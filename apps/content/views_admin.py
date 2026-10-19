"""Khu vực quản trị nội dung website."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import ROLE_GROUP_LEADER, has_full_scope, has_perm
from apps.core.audit import log_action
from apps.core.crud import AdminCreateView, AdminDeleteView, AdminDetailView, AdminListView, AdminUpdateView
from apps.core.downloads import serve_protected
from apps.core.images import optimize_image_field
from apps.core.models import AuditLog
from apps.core.permissions_mixins import owns_or_scoped, require_perm
from apps.core.workflow import Status, apply_transition, available_transitions, can_transition

from . import forms
from .models import (
    Album,
    Announcement,
    Category,
    Disclosure,
    DisclosureSection,
    DisclosureVersion,
    MediaItem,
    Page,
    Post,
    PublicDocument,
    StaffProfile,
)

# kind trên URL → (model, module, tiền tố tên URL)
KINDS = {
    "tin-tuc": (Post, "news", "content:news"),
    "thong-bao": (Announcement, "announcement", "content:announcement"),
    "trang": (Page, "page", "content:page"),
    "album": (Album, "album", "content:album"),
    "tai-lieu": (PublicDocument, "public_document", "content:pubdoc"),
    "cong-khai": (Disclosure, "disclosure", "content:disclosure"),
}
KIND_OF_MODEL = {v[0]: k for k, v in KINDS.items()}


def scope_content(user, qs):
    """Người dùng không có phạm vi toàn trường chỉ thấy nội dung mình tạo (tổ trưởng: cả tổ)."""
    if has_full_scope(user):
        return qs
    cond = Q(created_by=user)
    if user.role == ROLE_GROUP_LEADER and user.group_id and "group" in {f.name for f in qs.model._meta.fields}:
        cond |= Q(group_id=user.group_id)
    return qs.filter(cond)


def history_for(obj):
    return AuditLog.objects.filter(object_type=obj._meta.label, object_id=str(obj.pk)).select_related("user")[:50]


class ScopedListMixin:
    def scope_queryset(self, qs):
        return scope_content(self.request.user, qs)


class WorkflowDetailMixin:
    template_name = "content/admin_detail.html"
    body_template = ""

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not (has_full_scope(self.request.user) or owns_or_scoped(self.request.user, obj)):
            raise PermissionDenied
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx.update(
            transitions=available_transitions(self.request.user, obj, self.module),
            kind=KIND_OF_MODEL[type(obj)],
            history=history_for(obj),
            body_template=self.body_template,
            can_modify=self.can_modify(obj) and has_perm(self.request.user, self.module, "edit"),
            can_remove=self.can_modify(obj) and has_perm(self.request.user, self.module, "delete"),
            blockers=getattr(obj, "publish_blockers", lambda: [])(),
        )
        return ctx


@require_POST
def transition(request, kind, pk, name):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if kind not in KINDS:
        raise Http404
    model, module, prefix = KINDS[kind]
    obj = get_object_or_404(model, pk=pk)
    if not can_transition(request.user, obj, module, name):
        raise PermissionDenied
    if name == "publish":
        blockers = getattr(obj, "publish_blockers", lambda: [])()
        if blockers:
            for b in blockers:
                messages.error(request, b)
            return redirect(f"{prefix}_detail", pk=obj.pk)
    apply_transition(request, obj, module, name, note=request.POST.get("note", "").strip())
    messages.success(request, f"Đã chuyển trạng thái: {obj.get_status_display()}.")
    return redirect(f"{prefix}_detail", pk=obj.pk)


# --- Danh mục tin ----------------------------------------------------------------
class CategoryList(AdminListView):
    model = Category
    module = "news"
    page_title = "Danh mục tin"
    url_prefix = "content:category"
    columns = [("name", "Tên danh mục"), ("slug", "Đường dẫn"), ("order", "Thứ tự")]
    search_fields = ["name"]


class _CategoryEdit:
    model = Category
    form_class = forms.CategoryForm
    module = "news"
    url_prefix = "content:category"
    page_title = "Danh mục tin"

    def can_modify(self, obj):
        return has_perm(self.request.user, "news", "approve")


class CategoryCreate(_CategoryEdit, AdminCreateView):
    action = "approve"


class CategoryUpdate(_CategoryEdit, AdminUpdateView):
    action = "approve"


class CategoryDelete(_CategoryEdit, AdminDeleteView):
    action = "approve"


# --- Tin tức ------------------------------------------------------------------------
class PostList(ScopedListMixin, AdminListView):
    model = Post
    module = "news"
    page_title = "Tin tức"
    url_prefix = "content:news"
    columns = [
        ("title", "Tiêu đề"),
        ("category", "Danh mục"),
        ("status", "Trạng thái"),
        ("created_by", "Người tạo"),
        ("updated_at", "Cập nhật"),
    ]
    search_fields = ["title", "summary"]
    filter_fields = ["status", "category"]
    has_detail = True

    def get_queryset(self):
        return super().get_queryset().select_related("category", "created_by")


class _PostEdit:
    model = Post
    form_class = forms.PostForm
    module = "news"
    url_prefix = "content:news"
    page_title = "Tin bài"

    def after_save(self, form, obj, created):
        if "thumbnail" in form.changed_data and obj.thumbnail:
            optimize_image_field(obj.thumbnail)
            obj.save(update_fields=["thumbnail"])

    def get_success_url(self):
        return reverse("content:news_detail", kwargs={"pk": self.object.pk})


class PostCreate(_PostEdit, AdminCreateView):
    def get_initial(self):
        initial = super().get_initial()
        draft = self.request.session.pop("ai_draft_post", None)
        if draft:
            initial.update(title=draft.get("title", ""), body=draft.get("body", ""))
        return initial


class PostUpdate(_PostEdit, AdminUpdateView):
    pass


class PostDelete(_PostEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("content:news_list")


class PostDetail(WorkflowDetailMixin, AdminDetailView):
    model = Post
    module = "news"
    url_prefix = "content:news"
    page_title = "Tin bài"
    body_template = "content/detail_post.html"


# --- Thông báo ------------------------------------------------------------------
class AnnouncementList(ScopedListMixin, AdminListView):
    model = Announcement
    module = "announcement"
    page_title = "Thông báo"
    url_prefix = "content:announcement"
    columns = [("title", "Tiêu đề"), ("kind", "Loại"), ("status", "Trạng thái"), ("start_date", "Hiển thị từ"), ("end_date", "Hết hạn")]
    search_fields = ["title", "body"]
    filter_fields = ["status", "kind"]
    has_detail = True


class _AnnEdit:
    model = Announcement
    form_class = forms.AnnouncementForm
    module = "announcement"
    url_prefix = "content:announcement"
    page_title = "Thông báo"

    def get_success_url(self):
        return reverse("content:announcement_detail", kwargs={"pk": self.object.pk})


class AnnouncementCreate(_AnnEdit, AdminCreateView):
    pass


class AnnouncementUpdate(_AnnEdit, AdminUpdateView):
    pass


class AnnouncementDelete(_AnnEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("content:announcement_list")


class AnnouncementDetail(WorkflowDetailMixin, AdminDetailView):
    model = Announcement
    module = "announcement"
    url_prefix = "content:announcement"
    page_title = "Thông báo"
    body_template = "content/detail_announcement.html"


# --- Trang giới thiệu -------------------------------------------------------------
class PageList(ScopedListMixin, AdminListView):
    model = Page
    module = "page"
    page_title = "Trang giới thiệu"
    url_prefix = "content:page"
    columns = [("title", "Tiêu đề"), ("section", "Mục"), ("status", "Trạng thái"), ("order", "Thứ tự")]
    search_fields = ["title"]
    filter_fields = ["status", "section"]
    has_detail = True


class _PageEdit:
    model = Page
    form_class = forms.PageForm
    module = "page"
    url_prefix = "content:page"
    page_title = "Trang giới thiệu"

    def after_save(self, form, obj, created):
        if "image" in form.changed_data and obj.image:
            optimize_image_field(obj.image)
            obj.save(update_fields=["image"])

    def get_success_url(self):
        return reverse("content:page_detail", kwargs={"pk": self.object.pk})


class PageCreate(_PageEdit, AdminCreateView):
    pass


class PageUpdate(_PageEdit, AdminUpdateView):
    pass


class PageDelete(_PageEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("content:page_list")


class PageDetail(WorkflowDetailMixin, AdminDetailView):
    model = Page
    module = "page"
    url_prefix = "content:page"
    page_title = "Trang giới thiệu"
    body_template = "content/detail_post.html"


# --- Đội ngũ -------------------------------------------------------------------------
class StaffList(AdminListView):
    model = StaffProfile
    module = "staff_profile"
    page_title = "Đội ngũ (hiển thị công khai)"
    url_prefix = "content:staff"
    columns = [
        ("full_name", "Họ tên"),
        ("position", "Chức vụ"),
        ("staff_group", "Nhóm"),
        ("public_consent", "Đồng ý công khai"),
        ("is_visible", "Hiển thị"),
    ]
    search_fields = ["full_name", "position"]
    filter_fields = ["staff_group"]


class _StaffEdit:
    model = StaffProfile
    form_class = forms.StaffProfileForm
    module = "staff_profile"
    url_prefix = "content:staff"
    page_title = "Hồ sơ đội ngũ"

    def can_modify(self, obj):
        return True

    def after_save(self, form, obj, created):
        if "photo" in form.changed_data and obj.photo:
            optimize_image_field(obj.photo, max_dim=600)
            obj.save(update_fields=["photo"])


class StaffCreate(_StaffEdit, AdminCreateView):
    pass


class StaffUpdate(_StaffEdit, AdminUpdateView):
    pass


class StaffDelete(_StaffEdit, AdminDeleteView):
    pass


# --- Album ---------------------------------------------------------------------------
class AlbumList(ScopedListMixin, AdminListView):
    model = Album
    module = "album"
    page_title = "Thư viện ảnh/video"
    url_prefix = "content:album"
    columns = [("title", "Tên album"), ("kind", "Loại"), ("visibility", "Phạm vi"), ("status", "Trạng thái"), ("event_date", "Ngày")]
    search_fields = ["title", "description"]
    filter_fields = ["status", "kind", "school_year"]
    has_detail = True


class _AlbumEdit:
    model = Album
    form_class = forms.AlbumForm
    module = "album"
    url_prefix = "content:album"
    page_title = "Album"

    def get_success_url(self):
        return reverse("content:album_detail", kwargs={"pk": self.object.pk})


class AlbumCreate(_AlbumEdit, AdminCreateView):
    pass


class AlbumUpdate(_AlbumEdit, AdminUpdateView):
    pass


class AlbumDelete(_AlbumEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("content:album_list")


class AlbumDetail(WorkflowDetailMixin, AdminDetailView):
    model = Album
    module = "album"
    url_prefix = "content:album"
    page_title = "Album"
    body_template = "content/detail_album.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        ctx["upload_form"] = forms.MediaUploadForm(user=self.request.user)
        ctx["can_consent"] = has_perm(self.request.user, "album", "approve")
        return ctx


def _album_for_edit(request, pk):
    album = get_object_or_404(Album, pk=pk)
    if not (has_perm(request.user, "album", "edit") and owns_or_scoped(request.user, album)):
        raise PermissionDenied
    return album


@require_perm("album", "edit")
@require_POST
def album_upload(request, pk):
    album = _album_for_edit(request, pk)
    form = forms.MediaUploadForm(request.POST, request.FILES, user=request.user)
    if not form.is_valid():
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
        return redirect("content:album_detail", pk=album.pk)
    start = (album.items.aggregate(m=Max("order"))["m"] or 0) + 1
    created = 0
    with transaction.atomic():
        for i, f in enumerate(form.cleaned_data["images"]):
            item = MediaItem(
                album=album,
                media_type="image",
                caption=form.cleaned_data["caption"],
                has_children=form.cleaned_data["has_children"],
                uploaded_by=request.user,
                order=start + i,
            )
            item.image.save(f.name, f, save=False)
            optimize_image_field(item.image)
            item.save()
            created += 1
        if form.cleaned_data.get("video_url"):
            MediaItem.objects.create(
                album=album,
                media_type="video",
                video_url=form.cleaned_data["video_url"],
                caption=form.cleaned_data["caption"],
                has_children=form.cleaned_data["has_children"],
                uploaded_by=request.user,
                order=start + created,
            )
            created += 1
    log_action(request, "media_upload", album, module="album", changes={"count": created})
    messages.success(request, f"Đã tải lên {created} mục. Ảnh sẽ chỉ hiển thị công khai sau khi được xác nhận quyền sử dụng hình ảnh.")
    return redirect("content:album_detail", pk=album.pk)


@require_perm("album", "approve")
def media_consent(request, pk):
    item = get_object_or_404(MediaItem.objects.select_related("album"), pk=pk)
    form = forms.ConsentForm(
        request.POST or None, user=request.user, initial={"consent_status": item.consent_status, "consent_note": item.consent_note}
    )
    if request.method == "POST" and form.is_valid():
        old = item.consent_status
        item.consent_status = form.cleaned_data["consent_status"]
        item.consent_note = form.cleaned_data["consent_note"]
        item.consent_by = request.user
        item.consent_at = timezone.now()
        item.save()
        log_action(
            request,
            "media_consent",
            item.album,
            module="album",
            changes={"item": item.pk, "consent": [old, item.consent_status], "note": item.consent_note},
        )
        messages.success(request, "Đã cập nhật quyền sử dụng hình ảnh.")
        return redirect("content:album_detail", pk=item.album_id)
    return render(request, "content/media_consent.html", {"item": item, "form": form, "page_title": "Xác nhận quyền sử dụng hình ảnh"})


@require_perm("album", "edit")
def media_edit(request, pk):
    item = get_object_or_404(MediaItem.objects.select_related("album"), pk=pk)
    _album_for_edit(request, item.album_id)
    form = forms.MediaItemForm(request.POST or None, instance=item, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật chú thích.")
        return redirect("content:album_detail", pk=item.album_id)
    return render(
        request,
        "admin/generic_form.html",
        {
            "form": form,
            "page_title": "Sửa ảnh/video",
            "list_url": reverse("content:album_detail", args=[item.album_id]),
        },
    )


@require_perm("album", "delete")
@require_POST
def media_delete(request, pk):
    item = get_object_or_404(MediaItem, pk=pk)
    album = _album_for_edit(request, item.album_id)
    if item.image:
        item.image.delete(save=False)
    item.delete()
    log_action(request, "media_delete", album, module="album", changes={"item": pk})
    messages.success(request, "Đã xóa mục khỏi album.")
    return redirect("content:album_detail", pk=album.pk)


@require_perm("album", "view")
def media_file_admin(request, pk):
    item = get_object_or_404(MediaItem.objects.select_related("album"), pk=pk, media_type="image")
    if not (has_full_scope(request.user) or owns_or_scoped(request.user, item.album) or item.album.status == Status.PUBLISHED):
        raise PermissionDenied
    resp = serve_protected(item.image)
    resp["Content-Disposition"] = "inline"
    return resp


# --- Tài liệu tải xuống công khai -----------------------------------------------------
class PubDocList(ScopedListMixin, AdminListView):
    model = PublicDocument
    module = "public_document"
    page_title = "Tài liệu tải xuống"
    url_prefix = "content:pubdoc"
    columns = [
        ("title", "Tên tài liệu"),
        ("category", "Danh mục"),
        ("status", "Trạng thái"),
        ("download_count", "Lượt tải"),
        ("updated_at", "Cập nhật"),
    ]
    search_fields = ["title", "description"]
    filter_fields = ["status", "category"]
    has_detail = True


class _PubDocEdit:
    model = PublicDocument
    form_class = forms.PublicDocumentForm
    module = "public_document"
    url_prefix = "content:pubdoc"
    page_title = "Tài liệu tải xuống"

    def get_success_url(self):
        return reverse("content:pubdoc_detail", kwargs={"pk": self.object.pk})


class PubDocCreate(_PubDocEdit, AdminCreateView):
    pass


class PubDocUpdate(_PubDocEdit, AdminUpdateView):
    pass


class PubDocDelete(_PubDocEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("content:pubdoc_list")


class PubDocDetail(WorkflowDetailMixin, AdminDetailView):
    model = PublicDocument
    module = "public_document"
    url_prefix = "content:pubdoc"
    page_title = "Tài liệu tải xuống"
    body_template = "content/detail_file.html"


@require_perm("public_document", "view")
def pubdoc_download_admin(request, pk):
    doc = get_object_or_404(PublicDocument, pk=pk)
    if not (has_full_scope(request.user) or owns_or_scoped(request.user, doc)):
        raise PermissionDenied
    return serve_protected(doc.file, doc.title)


# --- Công khai giáo dục ------------------------------------------------------------------
class SectionList(AdminListView):
    model = DisclosureSection
    module = "disclosure"
    page_title = "Mục công khai"
    url_prefix = "content:section"
    columns = [("name", "Tên mục"), ("legal_basis", "Căn cứ"), ("order", "Thứ tự"), ("is_active", "Đang dùng")]


class _SectionEdit:
    model = DisclosureSection
    form_class = forms.DisclosureSectionForm
    module = "disclosure"
    url_prefix = "content:section"
    page_title = "Mục công khai"

    def can_modify(self, obj):
        return True


class SectionCreate(_SectionEdit, AdminCreateView):
    action = "approve"


class SectionUpdate(_SectionEdit, AdminUpdateView):
    action = "approve"


class SectionDelete(_SectionEdit, AdminDeleteView):
    action = "approve"


class DisclosureList(AdminListView):
    model = Disclosure
    module = "disclosure"
    page_title = "Công khai giáo dục"
    url_prefix = "content:disclosure"
    template_name = "content/disclosure_list.html"
    columns = [
        ("title", "Tiêu đề"),
        ("section", "Mục"),
        ("status", "Trạng thái"),
        ("disclosure_date", "Ngày công bố"),
        ("review_due", "Hạn rà soát"),
    ]
    search_fields = ["title", "description"]
    filter_fields = ["status", "section", "school_year"]
    has_detail = True

    def get_queryset(self):
        return super().get_queryset().select_related("section")


class _DisclosureEdit:
    model = Disclosure
    form_class = forms.DisclosureForm
    module = "disclosure"
    url_prefix = "content:disclosure"
    page_title = "Công khai giáo dục"

    def can_modify(self, obj):
        return True  # toàn bộ người có quyền disclosure.edit (mặc định: lãnh đạo, văn phòng)

    def after_save(self, form, obj, created):
        if created or {"file", "title", "description"} & set(form.changed_data):
            last = obj.versions.aggregate(m=Max("version_no"))["m"] or 0
            DisclosureVersion.objects.create(
                disclosure=obj,
                version_no=last + 1,
                title=obj.title,
                description=obj.description,
                file=obj.file.name if obj.file else "",
                note=form.cleaned_data.get("version_note", ""),
                created_by=self.request.user,
            )
        if not created and {"file", "title", "description"} & set(form.changed_data) and obj.authority_checked:
            # Nội dung đã thay đổi → cần kiểm tra lại
            obj.authority_checked = False
            obj.authority_checked_by = None
            obj.save(update_fields=["authority_checked", "authority_checked_by"])
            messages.warning(self.request, "Nội dung đã thay đổi: cần người có thẩm quyền kiểm tra lại trước khi công khai.")

    def get_success_url(self):
        return reverse("content:disclosure_detail", kwargs={"pk": self.object.pk})


class DisclosureCreate(_DisclosureEdit, AdminCreateView):
    pass


class DisclosureUpdate(_DisclosureEdit, AdminUpdateView):
    """Tệp cũ không bị xóa khi thay tệp mới: vẫn được giữ trong lịch sử phiên bản."""


class DisclosureDelete(_DisclosureEdit, AdminDeleteView):
    def get_success_url(self):
        return reverse("content:disclosure_list")


class DisclosureDetail(WorkflowDetailMixin, AdminDetailView):
    model = Disclosure
    module = "disclosure"
    url_prefix = "content:disclosure"
    page_title = "Công khai giáo dục"
    body_template = "content/detail_disclosure.html"

    def get_object(self, queryset=None):
        return AdminDetailView.get_object(self, queryset)

    def can_modify(self, obj):
        return True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["versions"] = self.object.versions.select_related("created_by")
        ctx["can_check"] = has_perm(self.request.user, "disclosure", "approve")
        ctx["check_form"] = forms.AuthorityCheckForm(user=self.request.user)
        return ctx


@require_perm("disclosure", "approve")
@require_POST
def disclosure_check(request, pk):
    obj = get_object_or_404(Disclosure, pk=pk)
    form = forms.AuthorityCheckForm(request.POST, user=request.user)
    if form.is_valid():
        obj.authority_checked = bool(form.cleaned_data["confirmed"])
        obj.authority_checked_by = request.user if obj.authority_checked else None
        obj.authority_note = form.cleaned_data["note"]
        obj.save(update_fields=["authority_checked", "authority_checked_by", "authority_note"])
        log_action(
            request, "authority_check", obj, module="disclosure", changes={"checked": obj.authority_checked, "note": obj.authority_note}
        )
        messages.success(request, "Đã cập nhật xác nhận kiểm tra.")
    return redirect("content:disclosure_detail", pk=obj.pk)


@require_perm("disclosure", "view")
def disclosure_download_admin(request, pk, version=None):
    obj = get_object_or_404(Disclosure, pk=pk)
    if version:
        v = get_object_or_404(DisclosureVersion, disclosure=obj, version_no=version)
        return serve_protected(v.file, f"{obj.title}-v{version}")
    return serve_protected(obj.file, obj.title)


@require_perm("announcement", "view")
def announcement_attachment_admin(request, pk):
    obj = get_object_or_404(Announcement, pk=pk)
    if not (has_full_scope(request.user) or owns_or_scoped(request.user, obj)):
        raise PermissionDenied
    return serve_protected(obj.attachment, obj.title)
