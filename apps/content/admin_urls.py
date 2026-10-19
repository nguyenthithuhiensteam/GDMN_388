from django.urls import path

from . import views_admin as v

app_name = "content"


def crud(prefix, slug, list_v, create_v, edit_v, delete_v, detail_v=None):
    pats = [
        path(f"{slug}/", list_v.as_view(), name=f"{prefix}_list"),
        path(f"{slug}/them/", create_v.as_view(), name=f"{prefix}_create"),
        path(f"{slug}/<int:pk>/sua/", edit_v.as_view(), name=f"{prefix}_edit"),
        path(f"{slug}/<int:pk>/xoa/", delete_v.as_view(), name=f"{prefix}_delete"),
    ]
    if detail_v:
        pats.append(path(f"{slug}/<int:pk>/", detail_v.as_view(), name=f"{prefix}_detail"))
    return pats


urlpatterns = [
    *crud("category", "danh-muc-tin", v.CategoryList, v.CategoryCreate, v.CategoryUpdate, v.CategoryDelete),
    *crud("news", "tin-tuc", v.PostList, v.PostCreate, v.PostUpdate, v.PostDelete, v.PostDetail),
    *crud(
        "announcement",
        "thong-bao",
        v.AnnouncementList,
        v.AnnouncementCreate,
        v.AnnouncementUpdate,
        v.AnnouncementDelete,
        v.AnnouncementDetail,
    ),
    *crud("page", "trang", v.PageList, v.PageCreate, v.PageUpdate, v.PageDelete, v.PageDetail),
    *crud("staff", "doi-ngu", v.StaffList, v.StaffCreate, v.StaffUpdate, v.StaffDelete),
    *crud("album", "album", v.AlbumList, v.AlbumCreate, v.AlbumUpdate, v.AlbumDelete, v.AlbumDetail),
    *crud("pubdoc", "tai-lieu", v.PubDocList, v.PubDocCreate, v.PubDocUpdate, v.PubDocDelete, v.PubDocDetail),
    *crud("section", "muc-cong-khai", v.SectionList, v.SectionCreate, v.SectionUpdate, v.SectionDelete),
    *crud("disclosure", "cong-khai", v.DisclosureList, v.DisclosureCreate, v.DisclosureUpdate, v.DisclosureDelete, v.DisclosureDetail),
    path("<slug:kind>/<int:pk>/chuyen/<slug:name>/", v.transition, name="transition"),
    path("album/<int:pk>/tai-len/", v.album_upload, name="album_upload"),
    path("anh/<int:pk>/", v.media_file_admin, name="media_file"),
    path("anh/<int:pk>/sua/", v.media_edit, name="media_edit"),
    path("anh/<int:pk>/xoa/", v.media_delete, name="media_delete"),
    path("anh/<int:pk>/quyen-hinh-anh/", v.media_consent, name="media_consent"),
    path("tai-lieu/<int:pk>/tai-xuong/", v.pubdoc_download_admin, name="pubdoc_download"),
    path("thong-bao/<int:pk>/dinh-kem/", v.announcement_attachment_admin, name="announcement_attachment"),
    path("cong-khai/<int:pk>/kiem-tra/", v.disclosure_check, name="disclosure_check"),
    path("cong-khai/<int:pk>/tai-xuong/", v.disclosure_download_admin, name="disclosure_download"),
    path("cong-khai/<int:pk>/tai-xuong/v<int:version>/", v.disclosure_download_admin, name="disclosure_download_version"),
]
