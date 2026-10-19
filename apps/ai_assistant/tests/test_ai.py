from unittest import mock

from django.test import override_settings
from django.urls import reverse

from apps.ai_assistant import service
from apps.core.tests.base import BaseTestCase
from apps.office.models import OfficialDocument


class AIDisabledTests(BaseTestCase):
    def test_pages_work_when_ai_not_configured(self):
        self.login(self.teacher)
        r = self.client.get(reverse("ai:index"))
        self.assertContains(r, "chưa được bật")
        with mock.patch.object(service, "generate") as gen:
            r = self.client.post(reverse("ai:draft_post"), {"topic": "Trung thu", "points": "Vui", "tone": "than-thien"})
            gen.assert_not_called()
        self.assertEqual(r.status_code, 200)

    def test_staff_without_ai_permission(self):
        self.login(self.staff)
        self.assertEqual(self.client.get(reverse("ai:index")).status_code, 403)
        # Tìm kiếm nội bộ không dùng AI nên vẫn dùng được, nhưng chỉ theo quyền
        self.assertEqual(self.client.get(reverse("ai:search") + "?q=ab").status_code, 200)

    def test_redaction(self):
        text = service.redact("Liên hệ 0912 345 678 hoặc a.b@example.com, CCCD 012345678901")
        self.assertNotIn("0912", text)
        self.assertNotIn("example.com", text)
        self.assertNotIn("012345678901", text)


@override_settings(AI_ENABLED=True, AI_API_KEY="test-key")
class AIEnabledTests(BaseTestCase):
    def setUp(self):
        p = mock.patch.object(service, "is_available", return_value=True)
        p.start()
        self.addCleanup(p.stop)

    def test_draft_post_goes_to_draft_form_not_published(self):
        self.login(self.teacher)
        with mock.patch.object(service, "generate", return_value="Tiêu đề gợi ý\nĐoạn 1\n<script>x</script>") as gen:
            r = self.client.post(reverse("ai:draft_post"), {"topic": "Trung thu", "points": "Vui", "tone": "than-thien"})
            gen.assert_called_once()
        self.assertContains(r, "Tiêu đề gợi ý")
        r = self.client.post(reverse("ai:save_post_draft"))
        self.assertRedirects(r, reverse("content:news_create"), fetch_redirect_response=False)
        r = self.client.get(reverse("content:news_create"))
        self.assertEqual(r.context["form"].initial["title"], "Tiêu đề gợi ý")
        self.assertNotIn("<script>", r.context["form"].initial["body"])
        from apps.content.models import Post

        self.assertFalse(Post.objects.exists())

    @override_settings(AI_ALLOW_INTERNAL_DOCUMENTS=False)
    def test_internal_document_not_sent_when_disallowed(self):
        doc = OfficialDocument.objects.create(number="1", issue_date="2026-10-01", summary="VB", issuer_text="X",
                                              content_text="Nội dung nội bộ")
        self.login(self.teacher)
        with mock.patch.object(service, "generate") as gen:
            r = self.client.post(reverse("ai:summarize") + f"?van_ban={doc.pk}", {"document_id": doc.pk})
            gen.assert_not_called()
        self.assertContains(r, "chưa cho phép")

    @override_settings(AI_ALLOW_INTERNAL_DOCUMENTS=True)
    def test_restricted_document_never_sent_and_no_access_escalation(self):
        restricted = OfficialDocument.objects.create(number="2", issue_date="2026-10-01", summary="Mật", issuer_text="X",
                                                     access_level="restricted", created_by=self.principal)
        managers = OfficialDocument.objects.create(number="3", issue_date="2026-10-01", summary="LĐ", issuer_text="X",
                                                   access_level="managers")
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("ai:summarize") + f"?van_ban={restricted.pk}").status_code, 404)
        self.login(self.vice)
        with mock.patch.object(service, "generate") as gen:
            self.client.post(reverse("ai:summarize") + f"?van_ban={managers.pk}", {"document_id": managers.pk})
            gen.assert_not_called()

    def test_ai_error_shown(self):
        self.login(self.teacher)
        with mock.patch.object(service, "generate", side_effect=service.AIError("Không kết nối được dịch vụ AI.")):
            r = self.client.post(reverse("ai:summarize"), {"text": "abc"})
        self.assertContains(r, "Không kết nối được")
