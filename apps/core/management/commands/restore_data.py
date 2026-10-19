"""Khôi phục dữ liệu từ bản sao lưu ZIP vào CSDL hiện tại (CSDL phải mới, đã migrate, chưa có dữ liệu nghiệp vụ).

CẢNH BÁO: thao tác ghi đè dữ liệu. Luôn chạy verify_backup --restore-test trước, và sao lưu hiện trạng."""
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Khôi phục dữ liệu và tệp từ bản sao lưu."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--yes", action="store_true", help="Xác nhận thực hiện.")
        parser.add_argument("--skip-media", action="store_true")

    def handle(self, *args, **opts):
        if not opts["yes"]:
            raise CommandError("Cần thêm --yes để xác nhận khôi phục (ghi đè dữ liệu).")
        call_command("verify_backup", opts["path"])
        from apps.accounts.models import User

        if User.objects.exists():
            raise CommandError("CSDL đích đã có tài khoản. Hãy khôi phục vào CSDL mới (đã migrate, chưa tạo tài khoản).")
        with zipfile.ZipFile(opts["path"]) as zf, tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "db.json"
            fixture.write_bytes(zf.read("db.json"))
            with transaction.atomic():
                call_command("prepare_restore")  # nạp lại đúng ma trận quyền/cấu hình đã sao lưu
                call_command("loaddata", str(fixture))
            if not opts["skip_media"]:
                for name in zf.namelist():
                    for label, root in (("media/", settings.MEDIA_ROOT), ("protected_media/", settings.PROTECTED_MEDIA_ROOT)):
                        if name.startswith(label) and not name.endswith("/"):
                            rel = Path(name[len(label):])
                            if ".." in rel.parts or rel.is_absolute():
                                raise CommandError(f"Đường dẫn không an toàn trong bản sao lưu: {name}")
                            dest = Path(root) / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open(name) as src, open(dest, "wb") as out:
                                shutil.copyfileobj(src, out)
            manifest = json.loads(zf.read("manifest.json"))
        self.stdout.write(self.style.SUCCESS(f"Đã khôi phục {manifest['objects']} bản ghi."))
