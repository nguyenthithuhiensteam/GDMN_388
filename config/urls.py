from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("tai-khoan/", include("apps.accounts.urls")),
    path("quan-tri/", include("apps.core.admin_urls")),
    path("quan-tri/tai-khoan/", include("apps.accounts.admin_urls")),
    path("quan-tri/to-chuc/", include("apps.org.urls")),
    path("quan-tri/noi-dung/", include("apps.content.admin_urls")),
    path("quan-tri/", include("apps.office.urls")),
    path("quan-tri/bao-cao/", include("apps.reports.urls")),
    path("quan-tri/ai/", include("apps.ai_assistant.urls")),
    path("", include("apps.content.public_urls")),
    path("", include("apps.core.public_urls")),
]

if settings.DEBUG:
    # Chỉ phục vụ tệp công khai khi phát triển; môi trường chính thức dùng Nginx.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "apps.core.views_public.error_403"
handler404 = "apps.core.views_public.error_404"
handler500 = "apps.core.views_public.error_500"
