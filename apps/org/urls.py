from django.urls import path

from . import views

app_name = "org"

urlpatterns = [
    path("<slug:entity>/", views.OrgList.as_view(), name="list"),
    path("<slug:entity>/them/", views.OrgCreate.as_view(), name="create"),
    path("<slug:entity>/<int:pk>/sua/", views.OrgUpdate.as_view(), name="edit"),
    path("<slug:entity>/<int:pk>/xoa/", views.OrgDelete.as_view(), name="delete"),
]
