"""Kiểm thử Giai đoạn 2: bảo vệ tài khoản quản trị, chống lạm dụng, truy cập trái phép theo vai trò."""

from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts import permissions as P
from apps.accounts.models import RolePermission, User, UserSession
from apps.core.models import AuditLog, SiteSettings
from apps.core.tests.base import BaseTestCase
from apps.core.tests.helpers import PASSWORD, make_user


class LastAdminProtectionTests(BaseTestCase):
    def _admin_form_data(self, **kw):
        data = {
            "username": "quantri",
            "full_name": "QT",
            "email": "",
            "phone": "",
            "role": P.ROLE_ADMIN,
            "position": "",
            "campus": "",
            "group": "",
            "is_active": "on",
            "password1": "",
            "password2": "",
        }
        data.update(kw)
        return data

    def test_is_last_active_admin(self):
        self.assertTrue(P.is_last_active_admin(self.admin))
        self.assertFalse(P.is_last_active_admin(self.principal))
        second = make_user("quantri2", P.ROLE_ADMIN)
        self.assertFalse(P.is_last_active_admin(self.admin))
        second.is_active = False
        second.save()
        self.assertTrue(P.is_last_active_admin(self.admin))

    def test_form_rejects_demoting_or_locking_last_admin(self):
        from apps.accounts.forms import UserAdminForm

        actor = make_user("quantri2", P.ROLE_ADMIN)
        actor.is_active = False  # chỉ còn self.admin đang hoạt động
        actor.save()
        for data in (self._admin_form_data(role=P.ROLE_PRINCIPAL), self._admin_form_data(is_active="")):
            form = UserAdminForm(data, instance=User.objects.get(pk=self.admin.pk), user=actor)
            self.assertFalse(form.is_valid())
            self.assertIn("duy nhất", " ".join(form.non_field_errors()))

    def test_admin_can_demote_another_admin_when_not_last(self):
        second = make_user("quantri2", P.ROLE_ADMIN)
        self.login(second)
        r = self.client.post(reverse("users:user_edit", args=[self.admin.pk]), self._admin_form_data(role=P.ROLE_PRINCIPAL))
        self.assertEqual(r.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, P.ROLE_PRINCIPAL)

    def test_cannot_delete_last_admin(self):
        actor = make_user("quantri2", P.ROLE_ADMIN)
        self.login(actor)
        User.objects.filter(pk=actor.pk).update(is_superuser=False)
        # Khi còn 2 quản trị: xóa được tài khoản kia
        victim = make_user("quantri3", P.ROLE_ADMIN)
        self.assertEqual(self.client.post(reverse("users:user_delete", args=[victim.pk])).status_code, 302)
        self.assertFalse(User.objects.filter(pk=victim.pk).exists())
        # Hiệu trưởng không bao giờ xóa/khóa được tài khoản quản trị
        self.login(self.principal)
        self.assertEqual(self.client.post(reverse("users:user_delete", args=[self.admin.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("users:user_lock", args=[self.admin.pk])).status_code, 403)


class PasswordResetThrottleTests(BaseTestCase):
    def test_reset_limited_per_ip_and_uniform_response(self):
        for _ in range(8):
            r = self.client.post(reverse("accounts:password_reset"), {"email": "giaovien@example.com"})
            self.assertRedirects(r, reverse("accounts:password_reset_done"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 5)
        self.assertTrue(AuditLog.objects.filter(action="password_reset_throttled").exists())

    def test_unknown_email_same_response(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "khong-ton-tai@example.com"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)


class SessionSecurityTests(BaseTestCase):
    def test_csrf_enforced_on_login_and_logout(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("accounts:login"), {"username": "giaovien", "password": PASSWORD})
        self.assertEqual(r.status_code, 403)
        c.force_login(self.teacher)
        self.assertEqual(c.post(reverse("accounts:logout")).status_code, 403)
        self.assertEqual(c.post(reverse("accounts:revoke_other_sessions")).status_code, 403)

    def test_session_key_rotates_on_login(self):
        self.client.get(reverse("accounts:login"))
        self.client.session["x"] = 1
        before = self.client.session.session_key
        self.client.post(reverse("accounts:login"), {"username": "giaovien", "password": PASSWORD})
        self.assertNotEqual(before, self.client.session.session_key)
        self.assertTrue(UserSession.objects.filter(session_key=self.client.session.session_key).exists())

    def test_no_open_redirect_after_login(self):
        r = self.client.post(
            reverse("accounts:login") + "?next=https://evil.example.com/",
            {"username": "giaovien", "password": PASSWORD, "next": "https://evil.example.com/"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("evil.example.com", r.url)

    def test_locked_user_existing_session_is_terminated(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)
        User.objects.filter(pk=self.teacher.pk).update(is_active=False)
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r.url)

    def test_cannot_revoke_other_users_session(self):
        other = Client()
        other.force_login(self.staff)
        staff_session = UserSession.objects.get(user=self.staff)
        self.login(self.teacher)
        self.assertEqual(self.client.post(reverse("accounts:revoke_session", args=[staff_session.pk])).status_code, 404)
        self.assertTrue(UserSession.objects.filter(pk=staff_session.pk).exists())

    def test_manager_revokes_user_sessions(self):
        other = Client()
        other.force_login(self.teacher)
        self.login(self.principal)
        self.client.post(reverse("users:user_revoke_sessions", args=[self.teacher.pk]))
        self.assertFalse(UserSession.objects.filter(user=self.teacher).exists())
        self.assertEqual(other.get(reverse("core:dashboard")).status_code, 302)
        # Hiệu trưởng không được thu hồi phiên của Quản trị hệ thống
        self.assertEqual(self.client.post(reverse("users:user_revoke_sessions", args=[self.admin.pk])).status_code, 403)
        self.login(self.teacher)
        self.assertEqual(self.client.post(reverse("users:user_revoke_sessions", args=[self.staff.pk])).status_code, 403)


class UnauthorizedWriteTests(BaseTestCase):
    """Người không đủ quyền gửi POST trực tiếp (không qua giao diện) phải bị từ chối và dữ liệu không đổi."""

    def test_non_admin_roles_cannot_modify_users_or_settings(self):
        name_before = SiteSettings.load().school_name
        for actor in (self.vice, self.office, self.leader, self.teacher, self.staff):
            self.login(actor)
            with self.subTest(role=actor.role):
                r = self.client.post(
                    reverse("users:user_create"),
                    {
                        "username": "hacker",
                        "full_name": "x",
                        "role": P.ROLE_ADMIN,
                        "password1": "Mat-khau-Tam-2026!",
                        "password2": "Mat-khau-Tam-2026!",
                    },
                )
                self.assertEqual(r.status_code, 403)
                self.assertEqual(self.client.post(reverse("users:user_lock", args=[self.staff.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse("users:user_delete", args=[self.staff.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse("users:permissions"), {}).status_code, 403)
                self.assertEqual(self.client.post(reverse("core:settings"), {"school_name": "Bị sửa"}).status_code, 403)
        self.assertFalse(User.objects.filter(username="hacker").exists())
        self.assertTrue(User.objects.get(pk=self.staff.pk).is_active)
        self.assertEqual(SiteSettings.load().school_name, name_before)
        self.assertTrue(RolePermission.objects.filter(allowed=True).exists())

    def test_anonymous_post_redirected_without_change(self):
        for url in (
            reverse("users:user_create"),
            reverse("users:user_lock", args=[self.staff.pk]),
            reverse("users:user_revoke_sessions", args=[self.staff.pk]),
            reverse("users:permissions"),
            reverse("core:settings"),
        ):
            r = self.client.post(url, {"username": "x", "role": P.ROLE_ADMIN})
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("accounts:login"), r.url)
        self.assertTrue(User.objects.get(pk=self.staff.pk).is_active)

    def test_admin_403_page_uses_admin_layout_and_is_logged(self):
        self.login(self.teacher)
        r = self.client.get(reverse("users:user_list"))
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Bạn không có quyền thực hiện thao tác này", status_code=403)
        self.assertContains(r, 'id="sidebar"', status_code=403)
        self.assertTrue(AuditLog.objects.filter(action="access_denied", user=self.teacher).exists())
        self.client.logout()
        r = self.client.get(reverse("public:home"))
        self.assertNotContains(r, 'id="sidebar"')


class UserDetailTests(BaseTestCase):
    def test_detail_visibility_and_effective_permissions(self):
        self.login(self.principal)
        r = self.client.get(reverse("users:user_detail", args=[self.teacher.pk]))
        self.assertEqual(r.status_code, 200)
        labels = [label for label, _ in r.context["permissions"]]
        self.assertIn("Kế hoạch giáo dục", labels)
        self.assertNotIn("Tài khoản người dùng", labels)
        self.assertTrue(r.context["can_edit"])
        r = self.client.get(reverse("users:user_detail", args=[self.admin.pk]))
        self.assertFalse(r.context["can_edit"])
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("users:user_detail", args=[self.staff.pk])).status_code, 403)
