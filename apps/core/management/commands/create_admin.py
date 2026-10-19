"""Tạo tài khoản Quản trị hệ thống theo quy trình an toàn.

Mật khẩu được nhập ẩn qua bàn phím (không lưu trong lịch sử lệnh) và phải đạt chính sách mật khẩu.
Chỉ dùng biến môi trường ADMIN_PASSWORD trong kịch bản tự động hóa có kiểm soát, và xóa biến ngay sau đó.
"""
import getpass
import os

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.accounts.permissions import ROLE_ADMIN


class Command(BaseCommand):
    help = "Tạo tài khoản Quản trị hệ thống (mật khẩu nhập ẩn)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument("--full-name", default="Quản trị hệ thống")

    def handle(self, *args, **opts):
        username = opts["username"].strip()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Tài khoản '{username}' đã tồn tại.")
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            password = getpass.getpass("Mật khẩu: ")
            if password != getpass.getpass("Nhập lại mật khẩu: "):
                raise CommandError("Mật khẩu nhập lại không khớp.")
        user = User(username=username, email=opts["email"], full_name=opts["full_name"], role=ROLE_ADMIN)
        try:
            password_validation.validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("Mật khẩu chưa đạt yêu cầu: " + " ".join(exc.messages))
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Đã tạo tài khoản quản trị '{username}'."))
