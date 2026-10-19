from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),
    path("xuat/<slug:fmt>/", views.report_export, name="export"),
    path("nhat-ky/xuat-excel/", views.audit_export, name="audit_export"),
]
