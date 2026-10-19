"""Chuẩn bị CSDL mới (đã migrate) để nạp bản sao lưu: xóa các dòng cấu hình mặc định do migration tạo,
tránh trùng khóa khi loaddata. Từ chối chạy nếu CSDL đã có tài khoản người dùng."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Dọn cấu hình mặc định trên CSDL mới trước khi khôi phục (nội bộ)."

    def handle(self, *args, **opts):
        from apps.accounts.models import RolePermission, User
        from apps.content.models import Category, DisclosureSection
        from apps.office.models import PlanExportTemplate
        from apps.org.models import Catalog

        if User.objects.exists():
            raise CommandError("CSDL đã có tài khoản; không dọn dữ liệu.")
        with transaction.atomic():
            for model in (RolePermission, Category, DisclosureSection, PlanExportTemplate, Catalog):
                model.objects.all().delete()
        self.stdout.write("Đã chuẩn bị CSDL để khôi phục.")
