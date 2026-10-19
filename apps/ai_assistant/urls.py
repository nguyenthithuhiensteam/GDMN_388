from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("", views.index, name="index"),
    path("tin-bai/", views.draft_post, name="draft_post"),
    path("tin-bai/dung-ban-nhap/", views.save_post_draft, name="save_post_draft"),
    path("ke-hoach/", views.draft_plan, name="draft_plan"),
    path("ke-hoach/dung-ban-nhap/", views.save_plan_draft, name="save_plan_draft"),
    path("tom-tat/", views.summarize, name="summarize"),
    path("minh-chung/", views.suggest_evidence, name="suggest_evidence"),
    path("bao-cao/", views.report_help, name="report_help"),
    path("tim-kiem/", views.internal_search, name="search"),
]
