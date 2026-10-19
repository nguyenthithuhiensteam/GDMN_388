from django.urls import path

from . import views_public as v

app_name = "public"

urlpatterns = [
    path("", v.home, name="home"),
    path("gioi-thieu/", v.about, name="about"),
    path("gioi-thieu/doi-ngu/", v.staff, name="staff"),
    path("trang/<slug:slug>/", v.page_detail, name="page_detail"),
    path("tin-tuc/", v.post_list, name="post_list"),
    path("tin-tuc/<slug:slug>/", v.post_detail, name="post_detail"),
    path("thong-bao/", v.announcement_list, name="announcement_list"),
    path("thong-bao/<slug:slug>/", v.announcement_detail, name="announcement_detail"),
    path("thong-bao/<slug:slug>/dinh-kem/", v.announcement_attachment, name="announcement_attachment"),
    path("tuyen-sinh/", v.admission, name="admission"),
    path("cong-khai/", v.disclosure_list, name="disclosure_list"),
    path("cong-khai/<int:pk>/tai-xuong/", v.disclosure_file, name="disclosure_file"),
    path("thu-vien-anh/", v.album_list, name="album_list"),
    path("thu-vien-anh/<slug:slug>/", v.album_detail, name="album_detail"),
    path("anh/<int:pk>/", v.media_public, name="media"),
    path("tai-lieu/", v.document_list, name="document_list"),
    path("tai-lieu/<int:pk>/tai-xuong/", v.document_download, name="document_download"),
    path("tim-kiem/", v.search, name="search"),
    path("xem-truoc/<slug:kind>/<int:pk>/", v.preview, name="preview"),
]
