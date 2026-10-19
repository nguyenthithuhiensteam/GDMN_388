from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Notification
from apps.core.tests.base import BaseTestCase
from apps.core.tests.helpers import pdf_file
from apps.office.models import EducationPlan, Evidence, EvidenceCategory, OfficialDocument, Task


class OfficialDocumentTests(BaseTestCase):
    def _doc(self, **kw):
        data = dict(
            direction="in",
            number="12",
            symbol="KH-PGD",
            issue_date=timezone.localdate(),
            issuer_text="Phòng GD",
            summary="Kế hoạch năm học",
            created_by=self.office,
        )
        data.update(kw)
        return OfficialDocument.objects.create(**data)

    def test_access_levels(self):
        public = self._doc(summary="Văn bản chung")
        managers = self._doc(summary="Văn bản lãnh đạo", access_level="managers")
        restricted = self._doc(summary="Văn bản mật", access_level="restricted", created_by=self.principal)
        restricted.allowed_users.add(self.vice)
        visible = set(OfficialDocument.objects.for_user(self.teacher))
        self.assertEqual(visible, {public})
        self.assertEqual(set(OfficialDocument.objects.for_user(self.office)), {public, managers})
        self.assertIn(restricted, OfficialDocument.objects.for_user(self.vice))
        self.assertIn(restricted, OfficialDocument.objects.for_user(self.principal))
        # Truy cập trực tiếp bằng URL
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("office:doc_detail", args=[restricted.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("office:doc_download", args=[managers.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("office:doc_edit", args=[public.pk])).status_code, 403)

    def test_create_search_and_download(self):
        self.login(self.office)
        r = self.client.post(
            reverse("office:doc_create"),
            {
                "direction": "in",
                "number": "45",
                "symbol": "CV-SGD",
                "issue_date": "15/09/2026",
                "issuer_text": "Sở GD&ĐT",
                "summary": "Hướng dẫn nhiệm vụ năm học",
                "content_text": "Nội dung",
                "file": pdf_file(),
                "processing_status": "new",
                "access_level": "all",
                "responsible": self.vice.pk,
            },
        )
        self.assertEqual(r.status_code, 302)
        doc = OfficialDocument.objects.get(number="45")
        self.assertTrue(Notification.objects.filter(user=self.vice).exists())
        r = self.client.get(reverse("office:doc_list") + "?q=CV-SGD&tu_ngay=01/09/2026&den_ngay=30/09/2026")
        self.assertContains(r, "Hướng dẫn nhiệm vụ")
        r = self.client.get(reverse("office:doc_list") + "?q=CV-SGD&tu_ngay=01/10/2026")
        self.assertNotContains(r, "Hướng dẫn nhiệm vụ năm học</a>")
        self.login(self.teacher)
        r = self.client.get(reverse("office:doc_download", args=[doc.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="download", user=self.teacher).exists())
        self.login(self.staff)
        self.assertEqual(self.client.get(reverse("office:doc_download", args=[doc.pk])).status_code, 200)

    def test_issuer_required(self):
        self.login(self.office)
        r = self.client.post(
            reverse("office:doc_create"),
            {
                "direction": "in",
                "number": "1",
                "issue_date": "15/09/2026",
                "summary": "X",
                "processing_status": "new",
                "access_level": "all",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(OfficialDocument.objects.exists())

    def test_export_excel_logged(self):
        self._doc()
        self.login(self.office)
        r = self.client.get(reverse("office:doc_export"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertTrue(AuditLog.objects.filter(action="export", module="official_doc").exists())
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("office:doc_export")).status_code, 403)


class PlanTests(BaseTestCase):
    def _create(self, user, level="theme", **kw):
        self.login(user)
        data = {
            "title": "KH chủ đề Gia đình",
            "level": level,
            "school_year": self.org["year"].pk,
            "group": self.org["g1"].pk,
            "school_class": self.org["cls"].pk,
            "content": "Nội dung v1",
            "version_note": "v1",
        }
        data.update(kw)
        r = self.client.post(reverse("office:plan_create"), data)
        self.assertEqual(r.status_code, 302, r.context and r.context["form"].errors)
        return EducationPlan.objects.latest("pk")

    def test_workflow_versions_and_permissions(self):
        plan = self._create(self.teacher)
        self.assertEqual(plan.status, "draft")
        self.assertEqual(plan.versions.count(), 1)
        self.client.post(
            reverse("office:plan_edit", args=[plan.pk]),
            {
                "title": plan.title,
                "level": "theme",
                "school_year": self.org["year"].pk,
                "group": self.org["g1"].pk,
                "school_class": self.org["cls"].pk,
                "content": "Nội dung v2",
                "version_note": "sửa",
            },
        )
        self.assertEqual(plan.versions.count(), 2)
        self.client.post(reverse("office:plan_transition", args=[plan.pk, "submit"]))
        plan.refresh_from_db()
        self.assertEqual(plan.status, "pending")
        # Không sửa được khi đã trình duyệt
        self.assertEqual(self.client.get(reverse("office:plan_edit", args=[plan.pk])).status_code, 403)
        # Giáo viên không tự duyệt
        self.assertEqual(self.client.post(reverse("office:plan_transition", args=[plan.pk, "approve"])).status_code, 403)
        # Giáo viên tổ khác không xem được
        self.login(self.teacher2)
        self.assertEqual(self.client.get(reverse("office:plan_detail", args=[plan.pk])).status_code, 404)
        # Tổ trưởng cùng tổ duyệt
        self.login(self.leader)
        self.client.post(reverse("office:plan_transition", args=[plan.pk, "approve"]), {"note": "Đạt"})
        plan.refresh_from_db()
        self.assertEqual(plan.status, "approved")
        self.assertEqual(plan.approved_by, self.leader)
        self.client.post(reverse("office:plan_transition", args=[plan.pk, "official"]))
        plan.refresh_from_db()
        self.assertEqual(plan.status, "official")
        self.assertTrue(Notification.objects.filter(user=self.teacher).exists())

    def test_leader_cannot_approve_school_plan(self):
        plan = self._create(self.vice, level="school", group="", school_class="")
        self.client.post(reverse("office:plan_transition", args=[plan.pk, "submit"]))
        self.login(self.leader)
        self.assertEqual(self.client.post(reverse("office:plan_transition", args=[plan.pk, "approve"])).status_code, 404)

    def test_teacher_cannot_create_school_plan(self):
        self.login(self.teacher)
        r = self.client.post(
            reverse("office:plan_create"), {"title": "KH trường", "level": "school", "school_year": self.org["year"].pk, "content": "x"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(EducationPlan.objects.exists())

    def test_comment_and_export(self):
        plan = self._create(self.teacher)
        self.client.post(reverse("office:plan_comment", args=[plan.pk]), {"content": "Góp ý thử"})
        self.assertEqual(plan.comments.count(), 1)
        r = self.client.get(reverse("office:plan_export", args=[plan.pk, "docx"]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("wordprocessingml", r["Content-Type"])
        r = self.client.get(reverse("office:plan_export", args=[plan.pk, "pdf"]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertEqual(self.client.get(reverse("office:plan_export", args=[plan.pk, "exe"])).status_code, 404)


class TaskTests(BaseTestCase):
    def test_assign_progress_confirm(self):
        self.login(self.leader)
        r = self.client.post(
            reverse("office:task_create"),
            {
                "title": "Nộp kế hoạch tuần",
                "description": "...",
                "assignee": self.teacher.pk,
                "due_date": "30/10/2026",
                "priority": "normal",
            },
        )
        self.assertEqual(r.status_code, 302)
        task = Task.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.teacher, message__contains="Nộp kế hoạch").exists())
        # Người khác tổ không thấy
        self.login(self.teacher2)
        self.assertEqual(self.client.get(reverse("office:task_detail", args=[task.pk])).status_code, 404)
        # Người được giao cập nhật và nộp minh chứng
        self.login(self.teacher)
        self.client.post(reverse("office:task_status", args=[task.pk]), {"status": "in_progress"})
        self.client.post(reverse("office:task_attach", args=[task.pk]), {"file": pdf_file(), "description": "MC"})
        self.assertEqual(task.attachments.count(), 1)
        # Người được giao không thể tự đánh dấu hoàn thành
        r = self.client.post(reverse("office:task_status", args=[task.pk]), {"status": "done"})
        task.refresh_from_db()
        self.assertNotEqual(task.status, "done")
        self.client.post(reverse("office:task_status", args=[task.pk]), {"status": "waiting", "note": "Đã xong"})
        task.refresh_from_db()
        self.assertEqual(task.status, "waiting")
        att = task.attachments.first()
        self.assertEqual(self.client.get(reverse("office:task_attachment", args=[att.pk])).status_code, 200)
        # Người giao xác nhận
        self.login(self.leader)
        self.client.post(reverse("office:task_status", args=[task.pk]), {"status": "done"})
        task.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertEqual(task.confirmed_by, self.leader)
        self.assertGreaterEqual(task.comments.filter(is_system=True).count(), 3)

    def test_leader_cannot_assign_outside_group(self):
        self.login(self.leader)
        r = self.client.post(reverse("office:task_create"), {"title": "Việc", "assignee": self.teacher2.pk, "priority": "normal"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Task.objects.exists())

    def test_teacher_cannot_create_task(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("office:task_create")).status_code, 403)

    def test_overdue_filter_and_display(self):
        t = Task.objects.create(
            title="Quá hạn", assignee=self.teacher, due_date=timezone.localdate() - timedelta(days=2), created_by=self.vice
        )
        self.assertTrue(t.is_overdue)
        self.assertEqual(t.display_status, "Quá hạn")
        self.login(self.teacher)
        r = self.client.get(reverse("office:task_list") + "?xem=qua-han")
        self.assertContains(r, "Quá hạn")
        self.assertEqual(r.context["progress"]["overdue"], 1)


class EvidenceTests(BaseTestCase):
    def test_versioning_no_overwrite_and_scope(self):
        cat = EvidenceCategory.objects.create(code="TC1", name="Tiêu chí 1")
        self.login(self.teacher)
        r = self.client.post(
            reverse("office:evidence_create"),
            {
                "code": "TC1.1",
                "title": "Biên bản sinh hoạt tổ",
                "category": cat.pk,
                "access_level": "all",
                "group": self.org["g1"].pk,
                "upload": pdf_file("v1.pdf"),
                "upload_note": "bản đầu",
            },
        )
        self.assertEqual(r.status_code, 302)
        ev = Evidence.objects.get()
        self.client.post(reverse("office:evidence_upload", args=[ev.pk]), {"file": pdf_file("v2.pdf"), "note": "bổ sung"})
        files = list(ev.files.order_by("version_no"))
        self.assertEqual([f.version_no for f in files], [1, 2])
        self.assertNotEqual(files[0].file.name, files[1].file.name)
        self.assertTrue(files[0].file.storage.exists(files[0].file.name))
        self.assertEqual(self.client.get(reverse("office:evidence_download", args=[ev.pk, 1])).status_code, 200)
        # Giáo viên tổ khác không thấy minh chứng của tổ này
        self.login(self.teacher2)
        self.assertEqual(self.client.get(reverse("office:evidence_detail", args=[ev.pk])).status_code, 404)
        # Nhân viên không có quyền tải
        self.login(self.staff)
        self.assertEqual(self.client.get(reverse("office:evidence_download", args=[ev.pk, 1])).status_code, 403)

    def test_export_requires_permission(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("office:evidence_export")).status_code, 403)
        self.login(self.office)
        r = self.client.get(reverse("office:evidence_export"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(module="evidence", action="export").exists())

    def test_teacher_cannot_manage_categories(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("office:evcat_create")).status_code, 403)
