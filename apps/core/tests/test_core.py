import io
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.content.models import Post
from apps.core.models import AuditLog, SiteSettings
from apps.core.sanitize import clean_html
from apps.core.tests.base import BaseTestCase


class DashboardTests(BaseTestCase):
    def test_dashboard_for_each_role(self):
        for user in (self.admin, self.principal, self.vice, self.office, self.leader, self.teacher, self.staff):
            self.login(user)
            r = self.client.get(reverse("core:dashboard"))
            self.assertEqual(r.status_code, 200, user.role)
        self.login(self.staff)
        r = self.client.get(reverse("core:dashboard"))
        labels = [c[0] for c in r.context["cards"]]
        self.assertNotIn("Tài khoản đang hoạt động", labels)
        self.login(self.admin)
        labels = [c[0] for c in self.client.get(reverse("core:dashboard")).context["cards"]]
        self.assertIn("Tài khoản đang hoạt động", labels)

    def test_sidebar_hides_unpermitted_menu(self):
        self.login(self.staff)
        r = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(r, reverse("users:user_list"))
        self.assertNotContains(r, reverse("core:settings"))


class SettingsTests(BaseTestCase):
    def test_edit_settings_requires_permission(self):
        self.login(self.vice)
        self.assertEqual(self.client.get(reverse("core:settings")).status_code, 200)
        self.assertEqual(self.client.post(reverse("core:settings"), {"school_name": "X"}).status_code, 403)
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("core:settings")).status_code, 403)

    def test_admin_updates_school_name_and_colors(self):
        self.login(self.admin)
        s = SiteSettings.load()
        data = {
            f.name: getattr(s, f.name)
            for f in SiteSettings._meta.fields
            if f.editable and f.name not in ("id", "logo", "banner", "updated_at", "demo_data_loaded")
        }
        data.update(school_name="TRƯỜNG MẦM NON HOA SEN", color_primary="#112233", map_embed_url="")
        data = {k: ("on" if v is True else "" if v in (False, None) else v) for k, v in data.items()}
        r = self.client.post(reverse("core:settings"), data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SiteSettings.load().school_name, "TRƯỜNG MẦM NON HOA SEN")
        self.assertContains(self.client.get("/"), "TRƯỜNG MẦM NON HOA SEN")
        self.assertContains(self.client.get("/"), "--mn-primary:#112233")
        data["color_primary"] = "red;}</style><script>"
        r = self.client.post(reverse("core:settings"), data)
        self.assertEqual(r.status_code, 200)
        data["color_primary"] = "#112233"
        data["map_embed_url"] = "https://evil.example.com/x"
        self.assertEqual(self.client.post(reverse("core:settings"), data).status_code, 200)


class AuditTests(BaseTestCase):
    def test_audit_visibility(self):
        AuditLog.objects.create(action="test", object_repr="abc")
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("core:audit")), "abc")
        self.login(self.principal)
        self.assertEqual(self.client.get(reverse("core:audit")).status_code, 200)
        self.login(self.vice)
        self.assertEqual(self.client.get(reverse("core:audit")).status_code, 403)
        self.login(self.admin)
        r = self.client.get(reverse("reports:audit_export"))
        self.assertEqual(r.status_code, 200)


class SanitizeTests(BaseTestCase):
    def test_clean_html(self):
        dirty = '<p onclick="x()">Hi<script>alert(1)</script><a href="javascript:alert(1)">l</a><img src=x onerror=alert(1)></p>'
        out = clean_html(dirty)
        self.assertNotIn("script", out)
        self.assertNotIn("onclick", out)
        self.assertNotIn("javascript:", out)
        self.assertNotIn("onerror", out)


class NotificationTests(BaseTestCase):
    def test_open_redirect_blocked(self):
        from apps.core.models import Notification

        n = Notification.objects.create(user=self.teacher, message="x", url="https://evil.example.com/")
        self.login(self.teacher)
        r = self.client.post(reverse("core:notification_read", args=[n.pk]))
        self.assertEqual(r.url, reverse("core:notifications"))
        other = Notification.objects.create(user=self.staff, message="y")
        self.assertEqual(self.client.post(reverse("core:notification_read", args=[other.pk])).status_code, 404)


class BackupTests(BaseTestCase):
    def test_backup_verify_and_tamper_detection(self):
        from apps.content.models import Category

        Post.objects.create(title="Bài sao lưu", category=Category.objects.first(), body="x")
        out = io.StringIO()
        call_command("backup_data", stdout=out)
        backups = sorted(Path(settings.BACKUP_DIR).glob("backup-*.zip"))
        self.assertEqual(len(backups), 1)
        call_command("verify_backup", str(backups[0]), stdout=io.StringIO())
        # Bản sao lưu bị sửa → phát hiện
        tampered = Path(settings.BACKUP_DIR) / "tampered.zip"
        with zipfile.ZipFile(backups[0]) as src, zipfile.ZipFile(tampered, "w") as dst:
            for item in src.namelist():
                data = src.read(item)
                if item == "db.json":
                    data = data.replace("Bài sao lưu".encode(), "Bài bị sửa".encode())
                dst.writestr(item, data)
        with self.assertRaises(CommandError):
            call_command("verify_backup", str(tampered), stdout=io.StringIO())

    def test_restore_test_into_temp_db(self):
        call_command("backup_data", "--no-media", stdout=io.StringIO())
        backup = sorted(Path(settings.BACKUP_DIR).glob("backup-*.zip"))[-1]
        out = io.StringIO()
        call_command("verify_backup", str(backup), "--restore-test", stdout=out)
        self.assertIn("THÀNH CÔNG", out.getvalue())

    def test_restore_refuses_non_empty_db(self):
        call_command("backup_data", "--no-media", stdout=io.StringIO())
        backup = sorted(Path(settings.BACKUP_DIR).glob("backup-*.zip"))[-1]
        with self.assertRaises(CommandError):
            call_command("restore_data", str(backup))
        with self.assertRaises(CommandError):
            call_command("restore_data", str(backup), "--yes", stdout=io.StringIO())


class CommandTests(BaseTestCase):
    def test_reminders_and_cleanup(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.core.models import Notification
        from apps.office.models import Task

        Task.objects.create(title="Sắp hạn", assignee=self.teacher, due_date=timezone.localdate() + timedelta(days=1))
        call_command("send_reminders", stdout=io.StringIO())
        self.assertTrue(Notification.objects.filter(user=self.teacher, message__contains="Sắp hạn").exists())
        call_command("cleanup_data", "--dry-run", stdout=io.StringIO())

    def test_create_admin_validates_password(self):
        from apps.accounts.models import User

        with mock.patch.dict("os.environ", {"ADMIN_PASSWORD": "123"}):
            with self.assertRaises(CommandError):
                call_command("create_admin", "--username", "qt2", stdout=io.StringIO())
        with mock.patch.dict("os.environ", {"ADMIN_PASSWORD": "Mot-Mat-Khau-Rat-Manh-2026"}):
            call_command("create_admin", "--username", "qt2", stdout=io.StringIO())
        self.assertEqual(User.objects.get(username="qt2").role, "quan_tri")

    def test_seed_demo_and_remove(self):
        from apps.accounts.models import User

        call_command("seed_demo", stdout=io.StringIO())
        self.assertTrue(SiteSettings.load().demo_data_loaded)
        self.assertTrue(Post.objects.filter(title__startswith="[MẪU]").exists())
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("core:dashboard")), "DỮ LIỆU MẪU")
        call_command("seed_demo", "--remove", stdout=io.StringIO())
        self.assertFalse(Post.objects.filter(title__startswith="[MẪU]").exists())
        self.assertFalse(User.objects.filter(username__startswith="mau_").exists())
        self.assertFalse(SiteSettings.load().demo_data_loaded)
