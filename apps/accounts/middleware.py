from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import UserSession


class ActiveSessionMiddleware:
    """
    - Đăng xuất phiên đã bị thu hồi (không còn trong UserSession).
    - Buộc đổi mật khẩu khi tài khoản được đánh dấu must_change_password.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            key = request.session.session_key
            tracked = UserSession.objects.filter(session_key=key, user=user).only("pk", "last_seen").first() if key else None
            if tracked is None:
                logout(request)
                return redirect(reverse("accounts:login") + "?revoked=1")
            if timezone.now() - tracked.last_seen > timedelta(minutes=5):
                UserSession.objects.filter(pk=tracked.pk).update(last_seen=timezone.now())
            if user.must_change_password:
                allowed = {reverse("accounts:password_change"), reverse("accounts:logout")}
                if request.path not in allowed and not request.path.startswith("/static/"):
                    return redirect("accounts:password_change")
        return self.get_response(request)
