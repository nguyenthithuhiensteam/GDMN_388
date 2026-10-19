from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("dang-nhap/", views.LoginView.as_view(), name="login"),
    path("dang-xuat/", auth_views.LogoutView.as_view(), name="logout"),
    path("doi-mat-khau/", views.PasswordChangeView.as_view(), name="password_change"),
    path("ho-so/", views.profile, name="profile"),
    path("phien/<int:pk>/thu-hoi/", views.revoke_session, name="revoke_session"),
    path("phien/thu-hoi-tat-ca/", views.revoke_other_sessions, name="revoke_other_sessions"),
    path(
        "quen-mat-khau/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "quen-mat-khau/da-gui/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "dat-lai/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html", success_url=reverse_lazy("accounts:password_reset_complete")
        ),
        name="password_reset_confirm",
    ),
    path(
        "dat-lai/hoan-tat/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
