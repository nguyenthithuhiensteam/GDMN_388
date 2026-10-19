from django.urls import reverse

from apps.core.models import AuditLog
from apps.core.tests.base import BaseTestCase
from apps.office.models import Task


class ReportTests(BaseTestCase):
    def test_report_permissions_and_scope(self):
        Task.objects.create(title="A", assignee=self.teacher, created_by=self.vice)
        Task.objects.create(title="B", assignee=self.teacher2, created_by=self.vice)
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("reports:index")).status_code, 403)
        self.login(self.leader)
        r = self.client.get(reverse("reports:index"))
        self.assertEqual(r.status_code, 200)
        task_section = [s for s in r.context["sections"] if s[0] == "Tiến độ nhiệm vụ"][0]
        total = [row for row in task_section[2] if row[0] == "Tổng"][0][1]
        self.assertEqual(total, 0)  # tổ trưởng không thấy việc giao riêng cho người khác ngoài tổ
        self.assertEqual(self.client.get(reverse("reports:export", args=["xlsx"])).status_code, 403)
        self.login(self.vice)
        r = self.client.get(reverse("reports:index") + "?date_from=01/01/2020")
        task_section = [s for s in r.context["sections"] if s[0] == "Tiến độ nhiệm vụ"][0]
        self.assertEqual([row for row in task_section[2] if row[0] == "Tổng"][0][1], 2)
        for fmt, ctype in (("xlsx", "spreadsheetml"), ("pdf", "pdf")):
            r = self.client.get(reverse("reports:export", args=[fmt]))
            self.assertEqual(r.status_code, 200)
            self.assertIn(ctype, r["Content-Type"])
        self.assertEqual(AuditLog.objects.filter(module="report").count(), 2)
        self.assertEqual(self.client.get(reverse("reports:export", args=["doc"])).status_code, 404)

    def test_excel_formula_injection_escaped(self):
        from apps.reports.exporters import _safe_cell

        self.assertEqual(_safe_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(_safe_cell("Bình thường"), "Bình thường")
