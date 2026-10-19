"""Áp dụng chính sách lưu giữ dữ liệu (chạy định kỳ). Thời hạn cấu hình bằng biến môi trường."""

import os
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone


def _days(name, default):
    return int(os.environ.get(name, default))


class Command(BaseCommand):
    help = "Xóa dữ liệu đã hết thời hạn lưu giữ."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        from apps.accounts.models import LoginAttempt, UserSession
        from apps.core.models import AuditLog, ContactMessage, Notification

        now = timezone.now()

        def before(env_name, default):
            return now - timedelta(days=_days(env_name, default))

        rules = [
            ("Lịch sử đăng nhập", LoginAttempt.objects.filter(created_at__lt=before("RETENTION_LOGIN_DAYS", 180))),
            ("Nhắc việc đã đọc", Notification.objects.filter(is_read=True, created_at__lt=before("RETENTION_NOTIFICATION_DAYS", 180))),
            ("Liên hệ đã xử lý", ContactMessage.objects.filter(status="done", created_at__lt=before("RETENTION_CONTACT_DAYS", 730))),
            ("Nhật ký hệ thống", AuditLog.objects.filter(created_at__lt=before("RETENTION_AUDIT_DAYS", 1825))),
            ("Phiên hết hạn", Session.objects.filter(expire_date__lt=now)),
        ]
        for label, qs in rules:
            count = qs.count()
            if not opts["dry_run"]:
                qs.delete()
            self.stdout.write(f"{label}: {count}{' (thử)' if opts['dry_run'] else ''}")
        if not opts["dry_run"]:
            live = set(Session.objects.values_list("session_key", flat=True))
            UserSession.objects.exclude(session_key__in=live).delete()
        self.stdout.write(self.style.SUCCESS("Hoàn tất."))
