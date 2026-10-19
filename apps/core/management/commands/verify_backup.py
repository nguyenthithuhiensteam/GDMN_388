"""Kiểm tra bản sao lưu: tính toàn vẹn (SHA-256), đọc được JSON, và (tùy chọn) khôi phục thử
vào một CSDL SQLite tạm để chứng minh có thể phục hồi."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Kiểm tra bản sao lưu. Dùng --restore-test để khôi phục thử vào CSDL tạm."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--restore-test", action="store_true")

    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError("Không tìm thấy tệp sao lưu.")
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                raise CommandError(f"Tệp ZIP bị hỏng tại: {bad}")
            manifest = json.loads(zf.read("manifest.json"))
            data = zf.read("db.json")
            if hashlib.sha256(data).hexdigest() != manifest["db_sha256"]:
                raise CommandError("Mã kiểm tra dữ liệu không khớp: bản sao lưu có thể đã bị thay đổi.")
            objects = json.loads(data)
            if len(objects) != manifest["objects"]:
                raise CommandError("Số bản ghi không khớp manifest.")
            for label, count in manifest.get("files", {}).items():
                actual = sum(1 for n in zf.namelist() if n.startswith(label + "/"))
                if actual != count:
                    raise CommandError(f"Số tệp {label} không khớp ({actual}/{count}).")
        self.stdout.write(self.style.SUCCESS(f"Toàn vẹn OK: {manifest['objects']} bản ghi, tệp: {manifest.get('files')}"))
        if opts["restore_test"]:
            self._restore_test(data)

    def _restore_test(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "restore.sqlite3"
            fixture = Path(tmp) / "db.json"
            fixture.write_bytes(data)
            env = {
                **os.environ,
                "DB_ENGINE": "sqlite",
                "SQLITE_PATH": str(db),
                "DJANGO_ENV": "development",
                "DJANGO_SECRET_KEY": "restore-test-only",
            }
            manage = Path(settings.BASE_DIR) / "manage.py"
            for cmd in (["migrate", "--noinput"], ["prepare_restore"], ["loaddata", str(fixture)]):
                r = subprocess.run([sys.executable, str(manage), *cmd], env=env, capture_output=True, text=True)
                if r.returncode != 0:
                    raise CommandError(f"Khôi phục thử thất bại ở bước {cmd[0]}:\n{r.stderr[-2000:]}")
        self.stdout.write(self.style.SUCCESS("Khôi phục thử vào CSDL tạm: THÀNH CÔNG."))
