"""Website công khai: chỉ hiển thị nội dung đã xuất bản."""
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import has_full_scope, has_perm
from apps.core.downloads import serve_protected
from apps.core.permissions_mixins import owns_or_scoped
from apps.core.workflow import Status
from apps.org.models import Campus

from .models import (
    Album, Announcement, Category, Disclosure, DisclosureSection, MediaItem, Page, Post, PublicDocument, StaffProfile,
)


def _paginate(request, qs, per_page=9):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


def home(request):
    posts = Post.objects.published().select_related("category")
    return render(request, "public/home.html", {
        "latest_posts": posts[:6],
        "featured_posts": posts.filter(is_featured=True)[:3],
        "announcements": Announcement.visible()[:5],
        "urgent": Announcement.visible().filter(kind="urgent")[:3],
        "albums": Album.objects.published().filter(visibility="public")[:4],
        "admission": Announcement.visible().filter(kind="admission").first(),
        "program_page": Page.objects.published().filter(section="chuong-trinh").first(),
    })


def post_list(request):
    qs = Post.objects.published().select_related("category", "created_by")
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("danh-muc", "")
    category = None
    if cat:
        category = Category.objects.filter(slug=cat).first()
        qs = qs.filter(category=category) if category else qs.none()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q))
    return render(request, "public/post_list.html", {
        "page_obj": _paginate(request, qs), "categories": Category.objects.all(), "q": q, "category": category,
    })


def post_detail(request, slug):
    post = get_object_or_404(Post.objects.select_related("category", "created_by"), slug=slug, status=Status.PUBLISHED)
    Post.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
    related = Post.objects.published().filter(category=post.category).exclude(pk=post.pk)[:3]
    return render(request, "public/post_detail.html", {"post": post, "related": related})


def announcement_list(request):
    qs = Announcement.visible()
    kind = request.GET.get("loai", "")
    if kind in dict(Announcement.KINDS):
        qs = qs.filter(kind=kind)
    return render(request, "public/announcement_list.html", {
        "page_obj": _paginate(request, qs, 12), "kinds": Announcement.KINDS, "kind": kind,
    })


def announcement_detail(request, slug):
    obj = get_object_or_404(Announcement, slug=slug, status=Status.PUBLISHED)
    if not obj.is_active_now:
        raise Http404
    return render(request, "public/announcement_detail.html", {"obj": obj})


def announcement_attachment(request, slug):
    obj = get_object_or_404(Announcement, slug=slug, status=Status.PUBLISHED)
    if not obj.is_active_now or not obj.attachment:
        raise Http404
    return serve_protected(obj.attachment, obj.title)


def admission(request):
    return render(request, "public/admission.html", {
        "pages": Page.objects.published().filter(section="tuyen-sinh"),
        "announcements": Announcement.visible().filter(kind="admission"),
    })


def about(request):
    pages = Page.objects.published().exclude(section="khac").order_by("section", "order")
    labels = dict(Page.SECTIONS)
    sections = [(labels.get(k, k), list(g)) for k, g in groupby(pages, key=lambda p: p.section)]
    return render(request, "public/about.html", {
        "sections": sections, "campuses": Campus.objects.filter(is_active=True),
    })


def staff(request):
    qs = StaffProfile.objects.filter(is_visible=True)
    labels = dict(StaffProfile.GROUPS)
    groups = [(labels[k], list(g)) for k, g in groupby(qs, key=lambda s: s.staff_group)]
    return render(request, "public/staff.html", {"groups": groups})


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, status=Status.PUBLISHED)
    return render(request, "public/page_detail.html", {"page": page})


def disclosure_list(request):
    published = Disclosure.objects.published().select_related("school_year")
    sections = DisclosureSection.objects.filter(is_active=True).prefetch_related(
        Prefetch("items", queryset=published, to_attr="published_items")
    )
    return render(request, "public/disclosure_list.html", {"sections": sections})


def disclosure_file(request, pk):
    obj = get_object_or_404(Disclosure, pk=pk, status=Status.PUBLISHED)
    if not obj.file:
        raise Http404
    return serve_protected(obj.file, obj.title)


def album_list(request):
    qs = Album.objects.published().filter(visibility="public").select_related("school_year")
    return render(request, "public/album_list.html", {"page_obj": _paginate(request, qs, 12)})


def album_detail(request, slug):
    album = get_object_or_404(Album, slug=slug, status=Status.PUBLISHED, visibility="public")
    return render(request, "public/album_detail.html", {"album": album, "items": album.public_items()})


def media_public(request, pk):
    """Ảnh album chỉ được phục vụ công khai khi đủ điều kiện (đã xuất bản + đã xác nhận quyền)."""
    item = get_object_or_404(MediaItem.objects.select_related("album"), pk=pk, media_type="image")
    if not item.is_publicly_visible():
        raise Http404
    resp = serve_protected(item.image)
    resp["Content-Disposition"] = "inline"
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


def document_list(request):
    qs = PublicDocument.objects.published()
    cat = request.GET.get("danh-muc", "")
    if cat in dict(PublicDocument.CATEGORIES):
        qs = qs.filter(category=cat)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return render(request, "public/document_list.html", {
        "page_obj": _paginate(request, qs, 20), "categories": PublicDocument.CATEGORIES, "cat": cat, "q": q,
    })


def document_download(request, pk):
    doc = get_object_or_404(PublicDocument, pk=pk, status=Status.PUBLISHED)
    PublicDocument.objects.filter(pk=pk).update(download_count=F("download_count") + 1)
    return serve_protected(doc.file, doc.title)


def search(request):
    q = request.GET.get("q", "").strip()[:100]
    results = {}
    if len(q) >= 2:
        results = {
            "posts": Post.objects.published().filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q))[:20],
            "announcements": Announcement.visible().filter(Q(title__icontains=q) | Q(body__icontains=q))[:20],
            "documents": PublicDocument.objects.published().filter(Q(title__icontains=q) | Q(description__icontains=q))[:20],
        }
    return render(request, "public/search.html", {"q": q, "results": results})


PREVIEW_MODELS = {"tin-tuc": (Post, "news"), "trang": (Page, "page"), "thong-bao": (Announcement, "announcement")}


@login_required
def preview(request, kind, pk):
    """Xem trước nội dung chưa công khai, dùng giao diện công khai, chỉ cho người có quyền."""
    if kind not in PREVIEW_MODELS:
        raise Http404
    model, module = PREVIEW_MODELS[kind]
    obj = get_object_or_404(model, pk=pk)
    if not has_perm(request.user, module, "view") or not (
        has_full_scope(request.user) or owns_or_scoped(request.user, obj)
    ):
        raise PermissionDenied
    ctx = {"preview": True}
    if model is Post:
        ctx.update(post=obj, related=[])
        return render(request, "public/post_detail.html", ctx)
    if model is Page:
        ctx.update(page=obj)
        return render(request, "public/page_detail.html", ctx)
    ctx.update(obj=obj)
    return render(request, "public/announcement_detail.html", ctx)
