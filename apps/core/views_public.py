from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render

from .audit import client_ip
from .forms import ContactForm

CONTACT_LIMIT = 5  # số lần gửi tối đa / IP / giờ


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST":
        ip = client_ip(request) or "unknown"
        key = f"contact-rate:{ip}"
        count = cache.get(key, 0)
        if count >= CONTACT_LIMIT:
            messages.error(request, "Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau.")
        elif form.is_valid():
            obj = form.save(commit=False)
            obj.ip_address = client_ip(request)
            obj.save()
            cache.set(key, count + 1, 3600)
            messages.success(request, "Cảm ơn bạn đã liên hệ. Nhà trường sẽ phản hồi sớm.")
            return redirect("site:contact")
    return render(request, "public/contact.html", {"form": form})


def error_403(request, exception=None):
    """Trang 403: trong khu quản trị dùng giao diện quản trị và ghi nhật ký lần truy cập bị từ chối."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and request.path.startswith(("/quan-tri", "/tai-khoan")):
        from .audit import log_action

        log_action(request, "access_denied", None, changes={"path": request.path[:200], "method": request.method})
        return render(request, "errors/403_admin.html", status=403)
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
