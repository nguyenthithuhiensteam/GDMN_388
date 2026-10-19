"""Sao lưu dữ liệu (JSON trung lập CSDL) + tệp tải lên vào một tệp ZIP có kiểm tra toàn vẹn.

Với PostgreSQL, nên kết hợp pg_dump (xem deploy/backup.sh). Bản sao lưu chứa dữ liệu nội bộ:
cần lưu trữ ở nơi an toàn, giới hạn quyền truy cập, và mã hóa khi chuyển ra ngoài máy chủ.
"""
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

EXCLUDE = ["contenttypes", "auth.permission", "sessions", "accounts.usersession"]


class Command(BaseCommand):
    help = "Tạo bản sao lưu dữ liệu và tệp vào BACKUP_DIR."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--keep", type=int, default=None, help="Số bản sao lưu giữ lại (mặc định BACKUP_KEEP).")
        parser.add_argument("--no-media", action="store_true", help="Không kèm tệp tải lên.")

    def handle(self, *args, **opts):
        out_dir = Path(opts["output_dir"] or settings.BACKUP_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o700)
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        target = out_dir / f"backup-{stamp}.zip"
        buf = io.StringIO()
        call_command("dumpdata", exclude=EXCLUDE, natural_foreign=True, indent=None, stdout=buf)
        data = buf.getvalue().encode("utf-8")
        manifest = {
            "created_at": timezone.now().isoformat(),
            "db_sha256": hashlib.sha256(data).hexdigest(),
            "objects": len(json.loads(data)),
            "files": {},
            "app_version": getattr(settings, "APP_VERSION", ""),
        }
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("db.json", data)
            if not opts["no_media"]:
                for label, root in (("media", settings.MEDIA_ROOT), ("protected_media", settings.PROTECTED_MEDIA_ROOT)):
                    root = Path(root)
                    count = 0
                    if root.exists():
                        for path in root.rglob("*"):
                            if path.is_file():
                                zf.write(path, f"{label}/{path.relative_to(root)}")
                                count += 1
                    manifest["files"][label] = count
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.chmod(target, 0o600)
        keep = opts["keep"] or settings.BACKUP_KEEP
        backups = sorted(out_dir.glob("backup-*.zip"), reverse=True)
        for old in backups[keep:]:
            old.unlink()
        self.stdout.write(self.style.SUCCESS(f"Đã sao lưu: {target} ({manifest['objects']} bản ghi)"))
        return str(target)
