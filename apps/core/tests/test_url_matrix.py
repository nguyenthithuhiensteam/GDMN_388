"""Kiểm tra có hệ thống: với MỌI vai trò, truy cập trực tiếp URL quản trị phải khớp ma trận phân quyền."""
from django.urls import reverse

from apps.accounts.permissions import has_perm
from apps.core.tests.base import BaseTestCase

# (tên URL, tham số, chức năng, thao tác)
ROUTES = [
    ("content:news_list", [], "news", "view"), ("content:news_create", [], "news", "create"),
    ("content:category_create", [], "news", "approve"),
    ("content:announcement_list", [], "announcement", "view"), ("content:announcement_create", [], "announcement", "create"),
    ("content:page_list", [], "page", "view"), ("content:page_create", [], "page", "create"),
    ("content:staff_list", [], "staff_profile", "view"), ("content:staff_create", [], "staff_profile", "create"),
    ("content:album_list", [], "album", "view"), ("content:album_create", [], "album", "create"),
    ("content:pubdoc_list", [], "public_document", "view"), ("content:pubdoc_create", [], "public_document", "create"),
    ("content:disclosure_list", [], "disclosure", "view"), ("content:disclosure_create", [], "disclosure", "create"),
    ("content:section_create", [], "disclosure", "approve"),
    ("office:doc_list", [], "official_doc", "view"), ("office:doc_create", [], "official_doc", "create"),
    ("office:doc_export", [], "official_doc", "export"),
    ("office:plan_list", [], "plan", "view"), ("office:plan_create", [], "plan", "create"),
    ("office:template_list", [], "plan", "approve"),
    ("office:task_list", [], "task", "view"), ("office:task_create", [], "task", "create"),
    ("office:task_export", [], "task", "export"),
    ("office:evidence_list", [], "evidence", "view"), ("office:evidence_create", [], "evidence", "create"),
    ("office:evidence_export", [], "evidence", "export"),
    ("reports:index", [], "report", "view"), ("reports:audit_export", [], "audit", "export"),
    ("users:user_list", [], "user", "view"), ("users:user_create", [], "user", "create"),
    ("users:permissions", [], "settings", "view"),
    ("org:list", ["lop"], "org", "view"), ("org:create", ["lop"], "org", "create"),
    ("core:settings", [], "settings", "view"), ("core:audit", [], "audit", "view"),
    ("core:contact_list", [], "contact", "view"),
    ("ai:index", [], "ai", "use"),
]


class UrlPermissionMatrixTests(BaseTestCase):
    def test_every_role_every_route(self):
        users = [self.principal, self.vice, self.office, self.leader, self.teacher, self.staff, self.admin]
        for user in users:
            self.login(user)
            for name, args, module, action in ROUTES:
                with self.subTest(role=user.role, url=name):
                    r = self.client.get(reverse(name, args=args))
                    allowed = has_perm(user, module, action)
                    if allowed:
                        self.assertEqual(r.status_code, 200, f"{user.role} cần truy cập được {name}")
                    else:
                        self.assertEqual(r.status_code, 403, f"{user.role} KHÔNG được truy cập {name}")
