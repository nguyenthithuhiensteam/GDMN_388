"""Dashboard riêng theo vai trò: đúng khối, đúng phạm vi dữ liệu, giao diện nền thống nhất."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.content.models import Category, Post
from apps.core.tests.base import BaseTestCase
from apps.core.workflow import Status
from apps.office.models import EducationPlan, Task

EXPECTED = {
    # vai trò: (khối bắt buộc có, khối không được có)
    "admin": ({"system", "failed_logins", "approvals", "my_tasks"}, set()),
    "principal": ({"approvals", "group_progress", "docs", "contacts", "my_tasks"}, {"system", "failed_logins", "my_group"}),
    "vice": ({"approvals", "group_progress", "docs", "contacts"}, {"system", "my_group"}),
    "office": ({"docs", "contacts", "my_tasks"}, {"approvals", "system", "group_progress", "my_group"}),
    "leader": ({"my_group", "approvals", "group_progress", "my_tasks", "my_plans", "my_content"}, {"system", "docs", "contacts"}),
    "teacher": ({"my_tasks", "my_plans", "my_content"}, {"approvals", "system", "docs", "contacts", "my_group", "group_progress"}),
    "staff": ({"my_tasks"}, {"approvals", "system", "docs", "contacts", "my_plans", "my_content", "my_group"}),
}


class DashboardPanelsByRoleTests(BaseTestCase):
    def _keys(self, user):
        self.login(user)
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 200)
        return {p["key"] for p in r.context["panels"]}, r

    def test_panels_match_role(self):
        users = {
            "admin": self.admin,
            "principal": self.principal,
            "vice": self.vice,
            "office": self.office,
            "leader": self.leader,
            "teacher": self.teacher,
            "staff": self.staff,
        }
        for name, user in users.items():
            must, must_not = EXPECTED[name]
            keys, r = self._keys(user)
            with self.subTest(role=name):
                self.assertTrue(must <= keys, f"{name} thiếu {must - keys}")
                self.assertFalse(must_not & keys, f"{name} không được thấy {must_not & keys}")
                for key in keys:
                    self.assertContains(r, f'data-panel="{key}"')

    def test_my_tasks_only_shows_own_work(self):
        due = timezone.localdate() + timedelta(days=2)
        Task.objects.create(title="Việc của GV1", assignee=self.teacher, due_date=due, created_by=self.vice)
        Task.objects.create(title="Việc của GV2", assignee=self.teacher2, due_date=due, created_by=self.vice)
        _, r = self._keys(self.teacher)
        self.assertContains(r, "Việc của GV1")
        self.assertNotContains(r, "Việc của GV2")

    def test_approval_queue_scoped(self):
        year, g1, g2 = self.org["year"], self.org["g1"], self.org["g2"]
        EducationPlan.objects.create(title="KH tổ MGL chờ duyệt", level="group", school_year=year, group=g1, status="pending")
        EducationPlan.objects.create(title="KH tổ NT chờ duyệt", level="group", school_year=year, group=g2, status="pending")
        EducationPlan.objects.create(title="KH trường chờ duyệt", level="school", school_year=year, status="pending")
        Post.objects.create(title="Tin chờ duyệt", category=Category.objects.first(), body="x", status=Status.PENDING)
        _, r = self._keys(self.leader)
        queue = next(p for p in r.context["panels"] if p["key"] == "approvals")
        texts = {i["text"] for i in queue["items"]}
        self.assertEqual(texts, {"KH tổ MGL chờ duyệt"})
        _, r = self._keys(self.principal)
        queue = next(p for p in r.context["panels"] if p["key"] == "approvals")
        texts = {i["text"] for i in queue["items"]}
        self.assertTrue({"KH tổ MGL chờ duyệt", "KH tổ NT chờ duyệt", "KH trường chờ duyệt", "Tin chờ duyệt"} <= texts)

    def test_admin_system_health_reports_missing_backup_and_single_admin(self):
        _, r = self._keys(self.admin)
        system = next(p for p in r.context["panels"] if p["key"] == "system")
        texts = {i["text"]: i for i in system["items"]}
        self.assertEqual(texts["Bản sao lưu gần nhất"]["badge"], "Chưa có")
        self.assertEqual(texts["Số tài khoản Quản trị hệ thống đang hoạt động"]["badge"], 1)

    def test_failed_login_visible_to_admin_only(self):
        self.client.post(reverse("accounts:login"), {"username": "giaovien", "password": "sai-mat-khau"})
        _, r = self._keys(self.admin)
        failed = next(p for p in r.context["panels"] if p["key"] == "failed_logins")
        self.assertEqual(failed["items"][0]["text"], "giaovien")


class UnifiedLayoutTests(BaseTestCase):
    def test_public_and_admin_share_base_layout(self):
        public = self.client.get(reverse("public:home")).content.decode()
        self.login(self.teacher)
        admin = self.client.get(reverse("core:dashboard")).content.decode()
        for html in (public, admin):
            self.assertEqual(html.count("css/site.css"), 1)
            self.assertEqual(html.count("bootstrap.bundle.min.js"), 1)
            self.assertIn('class="skip-link"', html)
            self.assertIn("--mn-primary:", html)
            self.assertIn('class="brand-logo"', html)
        self.assertIn('<body class="public">', public)
        self.assertIn('<body class="admin">', admin)
        self.assertIn('name="robots" content="noindex, nofollow"', admin)
        self.assertIn('aria-label="Đường dẫn"', admin)
