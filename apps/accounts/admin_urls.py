from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    # Quản lý tài khoản (khu vực quản trị)
    path("", views.UserList.as_view(), name="user_list"),
    path("them/", views.UserCreate.as_view(), name="user_create"),
    path("<int:pk>/sua/", views.UserUpdate.as_view(), name="user_edit"),
    path("<int:pk>/xoa/", views.UserDelete.as_view(), name="user_delete"),
    path("<int:pk>/khoa/", views.user_toggle_lock, name="user_lock"),
    path("phan-quyen/", views.permission_matrix, name="permissions"),
]
