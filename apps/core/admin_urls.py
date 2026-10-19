from django.urls import path

from . import views_admin as v

app_name = "core"

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("cau-hinh/", v.site_settings, name="settings"),
    path("nhat-ky/", v.audit_list, name="audit"),
    path("nhac-viec/", v.notifications, name="notifications"),
    path("nhac-viec/<int:pk>/doc/", v.notification_read, name="notification_read"),
    path("nhac-viec/doc-tat-ca/", v.notification_read_all, name="notification_read_all"),
    path("lien-he/", v.contact_list, name="contact_list"),
    path("lien-he/<int:pk>/", v.contact_detail, name="contact_detail"),
    path("lien-he/<int:pk>/xoa/", v.contact_delete, name="contact_delete"),
]
