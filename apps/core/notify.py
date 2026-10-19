"""Nhắc việc qua giao diện; gửi email nếu đã cấu hình EMAIL_NOTIFICATIONS_ENABLED."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification

logger = logging.getLogger(__name__)


def notify(users, message, url="", email=False):
    users = [u for u in users if u is not None and u.is_active]
    Notification.objects.bulk_create([Notification(user=u, message=message[:255], url=url[:255]) for u in users])
    if email and settings.EMAIL_NOTIFICATIONS_ENABLED:
        recipients = [u.email for u in users if u.email]
        if recipients:
            try:
                send_mail(f"[Nhắc việc] {message[:80]}", f"{message}\n\n{url}", None, recipients, fail_silently=False)
            except Exception:  # noqa: BLE001 - không để lỗi email làm hỏng thao tác chính
                logger.exception("Không gửi được email nhắc việc")
