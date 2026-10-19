"""Nhắc việc hằng ngày (chạy bằng cron/systemd timer): nhiệm vụ sắp/quá hạn, văn bản đến hạn,
nội dung công khai đến hạn rà soát."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import MANAGER_ROLES
from apps.core.models import SiteSettings
from apps.core.notify import notify


class Command(BaseCommand):
    help = "Tạo nhắc việc cho công việc sắp đến hạn/quá hạn."

    def handle(self, *args, **opts):
        from apps.content.models import Disclosure
        from apps.core.workflow import Status
        from apps.office.models import OfficialDocument, Task

        today = timezone.localdate()
        n = 0
        for t in Task.objects.open().filter(due_date__isnull=False, due_date__lte=today + timedelta(days=1)):
            targets = [t.assignee] if t.assignee else list(
                User.objects.filter(is_active=True, group=t.assigned_group) if t.assigned_group
                else User.objects.filter(is_active=True, campus=t.assigned_campus))
            label = "đã quá hạn" if t.due_date < today else "sắp đến hạn"
            notify(targets, f"Nhiệm vụ {label} ({t.due_date:%d/%m/%Y}): {t.title}",
                   reverse("office:task_detail", args=[t.pk]), email=True)
            n += 1
        for d in OfficialDocument.objects.filter(processing_status__in=["new", "processing"], deadline__isnull=False,
                                                 deadline__lte=today + timedelta(days=1)).exclude(responsible=None):
            notify([d.responsible], f"Văn bản đến hạn xử lý ({d.deadline:%d/%m/%Y}): {d}",
                   reverse("office:doc_detail", args=[d.pk]), email=True)
            n += 1
        days = SiteSettings.load().disclosure_review_days
        due = Disclosure.objects.exclude(status=Status.ARCHIVED).filter(review_due=today + timedelta(days=days))
        due = list(due) + list(Disclosure.objects.exclude(status=Status.ARCHIVED).filter(review_due=today))
        managers = list(User.objects.filter(is_active=True, role__in=MANAGER_ROLES))
        for d in due:
            notify([d.responsible] if d.responsible else managers, f"Đến hạn rà soát nội dung công khai: {d.title}",
                   reverse("content:disclosure_detail", args=[d.pk]), email=True)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Đã tạo {n} nhắc việc."))
