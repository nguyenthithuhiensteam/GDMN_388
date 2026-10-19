from django.urls import path

from . import views_public

app_name = "site"

urlpatterns = [
    path("lien-he/", views_public.contact, name="contact"),
]
