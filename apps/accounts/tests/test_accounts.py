from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.accounts import permissions as P
from apps.accounts.models import LoginAttempt, RolePermission, User, UserSession
from apps.core.models import AuditLog
from apps.core.tests.base import BaseTestCase
from apps.core.tests.helpers import PASSWORD


class LoginTests(BaseTestCase):
    def test_login_success_and_logout(self):
        r = self.client.post(reverse("accounts:login"), {"username": "giaovien", "password": PASSWORD})
        self.assertRedirects(r, reverse("core:dashboard"))
        self.assertTrue(UserSession.objects.filter(user=self.teacher).exists())
        self.assertTrue(AuditLog.objects.filter(action="login", user=self.teacher).exists())
        # Đăng xuất phải dùng POST
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        r = self.client.post(reverse("accounts:logout"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 302)

    def test_login_wrong_password(self):
        r = self.client.post(reverse("accounts:login"), {"username": "giaovien", "password": "sai"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "không đúng")
        self.assertTrue(LoginAttempt.objects.filter(username="giaovien", successful=False).exists())

    def test_lockout_after_max_failures(self):
        for _ in range(settings.LOGIN_MAX_FAILURES):
            self.client.post(reverse("accounts:login"), {"username": "giaovien", "password": "sai"})
        r = self.client.post(reverse("accounts:login"), {"username": "giaovien", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "quá nhiều lần")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_login(self):
        self.staff.is_active = False
        self.staff.save()
        r = self.client.post(reverse("accounts:login"), {"username": "nhanvien", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(r.status_code, 200)

    def test_must_change_password_redirect(self):
        self.teacher.must_change_password = True
        self.teacher.save()
        self.login(self.teacher)
        r = self.client.get(reverse("core:dashboard"))
        self.assertRedirects(r, reverse("accounts:password_change"))
        r = self.client.post(reverse("accounts:password_change"), {
            "old_password": PASSWORD, "new_password1": "Mat-khau-Moi-2026!", "new_password2": "Mat-khau-Moi-2026!"})
        self.assertEqual(r.status_code, 302)
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.must_change_password)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)

    def test_password_reset_sends_email(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "giaovien@example.com"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/tai-khoan/dat-lai/", mail.outbox[0].body)

    def test_revoke_other_session(self):
        from django.test import Client

        other = Client()
        other.force_login(self.teacher)
        self.login(self.teacher)
        self.assertEqual(other.get(reverse("core:dashboard")).status_code, 200)
        self.client.post(reverse("accounts:revoke_other_sessions"))
        r = other.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r.url)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)

    def test_profile_cannot_change_role(self):
        self.login(self.teacher)
        self.client.post(reverse("accounts:profile"), {"full_name": "GV Mới", "email": "a@b.vn", "phone": "", "role": P.ROLE_ADMIN})
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.full_name, "GV Mới")
        self.assertEqual(self.teacher.role, P.ROLE_TEACHER)


class PermissionMatrixTests(BaseTestCase):
    def test_defaults_seeded(self):
        self.assertTrue(RolePermission.objects.filter(role=P.ROLE_TEACHER, module="plan", action="create", allowed=True).exists())
        self.assertFalse(RolePermission.objects.get(role=P.ROLE_TEACHER, module="user", action="view").allowed)
        self.assertTrue(P.has_perm(self.admin, "settings", "edit"))
        self.assertFalse(P.has_perm(self.teacher, "news", "publish"))
        self.assertFalse(P.has_perm(self.principal, "user", "delete"))

    def test_only_admin_edits_matrix(self):
        self.login(self.principal)
        self.assertEqual(self.client.get(reverse("users:permissions")).status_code, 200)
        r = self.client.post(reverse("users:permissions"), {f"p__{P.ROLE_TEACHER}__user__view": "on"})
        self.assertEqual(r.status_code, 403)
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("users:permissions")).status_code, 403)

    def test_admin_changes_matrix_takes_effect(self):
        self.login(self.admin)
        data = {f"p__{r}__{m}__{a}": "on" for r, m, a in RolePermission.objects.filter(allowed=True).exclude(
            role=P.ROLE_ADMIN).values_list("role", "module", "action")}
        data[f"p__{P.ROLE_TEACHER}__report__view"] = "on"
        self.client.post(reverse("users:permissions"), data)
        self.assertTrue(RolePermission.objects.get(role=P.ROLE_TEACHER, module="report", action="view").allowed)
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("reports:index")).status_code, 200)


class UserManagementTests(BaseTestCase):
    def _payload(self, **kw):
        data = {"username": "moi", "full_name": "Người mới", "email": "moi@example.com", "phone": "", "role": P.ROLE_TEACHER,
                "position": "", "campus": "", "group": "", "is_active": "on",
                "password1": "Mat-khau-Tam-2026!", "password2": "Mat-khau-Tam-2026!"}
        data.update(kw)
        return data

    def test_admin_creates_user_with_temp_password(self):
        self.login(self.admin)
        r = self.client.post(reverse("users:user_create"), self._payload())
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="moi")
        self.assertTrue(u.must_change_password)
        self.assertTrue(u.check_password("Mat-khau-Tam-2026!"))

    def test_principal_cannot_assign_admin_role(self):
        self.login(self.principal)
        r = self.client.post(reverse("users:user_create"), self._payload(role=P.ROLE_ADMIN))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="moi").exists())

    def test_principal_cannot_edit_admin_account(self):
        self.login(self.principal)
        self.assertEqual(self.client.get(reverse("users:user_edit", args=[self.admin.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("users:user_lock", args=[self.admin.pk])).status_code, 403)

    def test_user_cannot_elevate_own_role(self):
        self.login(self.principal)
        data = self._payload(username="hieutruong", role=P.ROLE_ADMIN, password1="", password2="")
        self.client.post(reverse("users:user_edit", args=[self.principal.pk]), data)
        self.principal.refresh_from_db()
        self.assertEqual(self.principal.role, P.ROLE_PRINCIPAL)
        self.assertTrue(self.principal.is_active)

    def test_lock_and_unlock(self):
        self.login(self.admin)
        self.client.post(reverse("users:user_lock", args=[self.teacher.pk]), {"reason": "Nghỉ việc"})
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.is_active)
        self.assertEqual(self.teacher.locked_reason, "Nghỉ việc")
        self.client.post(reverse("users:user_lock", args=[self.teacher.pk]), {"reason": ""})
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.is_active)

    def test_cannot_lock_self(self):
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse("users:user_lock", args=[self.admin.pk])).status_code, 403)

    def test_teacher_cannot_access_user_management(self):
        self.login(self.teacher)
        for url in (reverse("users:user_list"), reverse("users:user_create"), reverse("users:user_edit", args=[self.staff.pk])):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_weak_password_rejected(self):
        self.login(self.admin)
        r = self.client.post(reverse("users:user_create"), self._payload(password1="123456", password2="123456"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="moi").exists())


class AnonymousAccessTests(BaseTestCase):
    @override_settings(DEBUG=False)
    def test_admin_urls_require_login(self):
        urls = ["/quan-tri/", "/quan-tri/tai-khoan/", "/quan-tri/van-ban/", "/quan-tri/ke-hoach/", "/quan-tri/nhiem-vu/",
                "/quan-tri/minh-chung/", "/quan-tri/bao-cao/", "/quan-tri/cau-hinh/", "/quan-tri/nhat-ky/",
                "/quan-tri/noi-dung/tin-tuc/", "/quan-tri/to-chuc/nam-hoc/", "/quan-tri/ai/", "/quan-tri/tai-khoan/phan-quyen/"]
        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("accounts:login"), r.url)
