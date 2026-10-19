from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.content.models import (
    Album, Announcement, Category, Disclosure, DisclosureSection, MediaItem, Post, PublicDocument,
)
from apps.core.models import AuditLog, ContactMessage, SiteSettings
from apps.core.tests.base import BaseTestCase
from apps.core.tests.helpers import pdf_file, png_file
from apps.core.workflow import Status


class PostWorkflowTests(BaseTestCase):
    def setUp(self):
        self.cat = Category.objects.first()

    def _create_post(self, user, **kw):
        self.login(user)
        data = {"title": "Ngày hội đến trường", "category": self.cat.pk, "summary": "Tóm tắt",
                "body": "<p>Nội dung <script>alert(1)</script><strong>đậm</strong></p>", "group": ""}
        data.update(kw)
        r = self.client.post(reverse("content:news_create"), data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        return Post.objects.latest("pk")

    def test_full_workflow_draft_to_published(self):
        post = self._create_post(self.teacher)
        self.assertEqual(post.status, Status.DRAFT)
        self.assertNotIn("<script>", post.body)
        self.assertIn("<strong>", post.body)
        # Chưa xuất bản → không xem được công khai
        self.client.logout()
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)
        # Giáo viên gửi duyệt
        self.login(self.teacher)
        self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, "submit"]))
        post.refresh_from_db()
        self.assertEqual(post.status, Status.PENDING)
        # Giáo viên không được tự duyệt/xuất bản (kể cả gõ trực tiếp URL)
        self.assertEqual(self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, "approve"])).status_code, 403)
        self.assertEqual(self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, "publish"])).status_code, 403)
        # Phó hiệu trưởng duyệt và xuất bản
        self.login(self.vice)
        self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, "approve"]), {"note": "OK"})
        self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, "publish"]))
        post.refresh_from_db()
        self.assertEqual(post.status, Status.PUBLISHED)
        self.assertEqual(post.approved_by, self.vice)
        self.assertIsNotNone(post.published_at)
        self.client.logout()
        r = self.client.get(post.get_absolute_url())
        self.assertContains(r, "Ngày hội đến trường")
        self.assertTrue(AuditLog.objects.filter(action="workflow:publish", object_id=str(post.pk)).exists())

    def test_publish_requires_approval_when_configured(self):
        post = self._create_post(self.vice)
        self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, "publish"]))
        post.refresh_from_db()
        self.assertEqual(post.status, Status.DRAFT)  # 403: phải duyệt trước

    def test_thumbnail_without_consent_blocks_publish(self):
        post = self._create_post(self.vice, thumbnail=png_file())
        self.assertTrue(post.thumbnail)
        for name in ("submit", "approve", "publish"):
            self.client.post(reverse("content:transition", args=["tin-tuc", post.pk, name]))
        post.refresh_from_db()
        self.assertEqual(post.status, Status.APPROVED)

    def test_teacher_cannot_edit_others_post(self):
        post = self._create_post(self.leader)
        self.login(self.teacher2)
        self.assertEqual(self.client.get(reverse("content:news_edit", args=[post.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("content:news_detail", args=[post.pk])).status_code, 403)

    def test_preview_permissions(self):
        post = self._create_post(self.teacher)
        url = reverse("public:preview", args=["tin-tuc", post.pk])
        self.assertContains(self.client.get(url), "XEM TRƯỚC")
        self.login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_public_list_search_and_pagination(self):
        now = timezone.now()
        for i in range(12):
            Post.objects.create(title=f"Bài số {i}", category=self.cat, body="x", status=Status.PUBLISHED, published_at=now)
        Post.objects.create(title="Bản nháp bí mật", category=self.cat, body="x", status=Status.DRAFT)
        r = self.client.get(reverse("public:post_list"))
        self.assertEqual(len(r.context["page_obj"]), 9)
        self.assertNotContains(r, "Bản nháp bí mật")
        r = self.client.get(reverse("public:post_list") + "?page=2")
        self.assertEqual(len(r.context["page_obj"]), 3)
        r = self.client.get(reverse("public:post_list") + "?q=số 1")
        self.assertContains(r, "Bài số 1")
        r = self.client.get(reverse("public:search") + "?q=bí mật")
        self.assertNotContains(r, "Bản nháp bí mật")
        r = self.client.get(reverse("content:news_list"))
        self.assertEqual(r.status_code, 302)

    def test_admin_list_filter_and_scope(self):
        self._create_post(self.teacher, title="Bài của giáo viên")
        self._create_post(self.teacher2, title="Bài của GV khác")
        self.login(self.teacher)
        r = self.client.get(reverse("content:news_list"))
        self.assertContains(r, "Bài của giáo viên")
        self.assertNotContains(r, "Bài của GV khác")
        self.login(self.vice)
        r = self.client.get(reverse("content:news_list") + "?q=khác&status=draft")
        self.assertContains(r, "Bài của GV khác")
        self.assertNotContains(r, "Bài của giáo viên")


class AnnouncementTests(BaseTestCase):
    def test_expired_announcement_hidden(self):
        today = timezone.localdate()
        a = Announcement.objects.create(title="Hết hạn", body="x", status=Status.PUBLISHED, start_date=today - timedelta(days=10),
                                        end_date=today - timedelta(days=1))
        b = Announcement.objects.create(title="Còn hạn", body="x", status=Status.PUBLISHED, start_date=today)
        r = self.client.get(reverse("public:announcement_list"))
        self.assertContains(r, "Còn hạn")
        self.assertNotContains(r, "Hết hạn")
        self.assertEqual(self.client.get(a.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(b.get_absolute_url()).status_code, 200)

    def test_attachment_only_when_visible(self):
        a = Announcement(title="Có tệp", body="x", status=Status.DRAFT)
        a.attachment.save("tb.pdf", pdf_file(), save=True)
        url = reverse("public:announcement_attachment", args=[a.slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        a.status = Status.PUBLISHED
        a.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])

    def test_invalid_end_date(self):
        self.login(self.vice)
        r = self.client.post(reverse("content:announcement_create"), {
            "title": "T", "kind": "school", "body": "x", "start_date": "10/10/2026", "end_date": "01/10/2026"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Announcement.objects.filter(title="T").exists())


class AlbumConsentTests(BaseTestCase):
    def test_photo_public_only_after_consent_and_publish(self):
        self.login(self.teacher)
        self.client.post(reverse("content:album_create"), {"title": "Trung thu", "kind": "event", "visibility": "public"})
        album = Album.objects.get(title="Trung thu")
        r = self.client.post(reverse("content:album_upload", args=[album.pk]),
                             {"images": [png_file("a.png"), png_file("b.png")], "caption": "Vui", "has_children": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(album.items.count(), 2)
        item = album.items.first()
        public_url = reverse("public:media", args=[item.pk])
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)
        # Giáo viên không được tự xác nhận quyền sử dụng hình ảnh
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse("content:media_consent", args=[item.pk])).status_code, 403)
        # Phó HT xác nhận phải có căn cứ
        self.login(self.vice)
        r = self.client.post(reverse("content:media_consent", args=[item.pk]), {"consent_status": "approved", "consent_note": ""})
        self.assertEqual(r.status_code, 200)
        self.client.post(reverse("content:media_consent", args=[item.pk]),
                         {"consent_status": "approved", "consent_note": "Phiếu đồng ý lưu VP"})
        item.refresh_from_db()
        self.assertEqual(item.consent_status, MediaItem.CONSENT_APPROVED)
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)  # album chưa xuất bản
        album.status = Status.PUBLISHED
        album.save()
        self.assertEqual(self.client.get(public_url).status_code, 200)
        other = album.items.exclude(pk=item.pk).first()
        self.assertEqual(self.client.get(reverse("public:media", args=[other.pk])).status_code, 404)
        r = self.client.get(album.get_absolute_url())
        self.assertEqual(len(r.context["items"]), 1)

    def test_reject_non_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.login(self.vice)
        album = Album.objects.create(title="A", created_by=self.vice)
        fake = SimpleUploadedFile("x.png", b"<?php echo 1; ?>", content_type="image/png")
        self.client.post(reverse("content:album_upload", args=[album.pk]), {"images": [fake]})
        self.assertEqual(album.items.count(), 0)


class DisclosureTests(BaseTestCase):
    def test_versions_and_authority_check(self):
        section = DisclosureSection.objects.first()
        self.login(self.office)
        r = self.client.post(reverse("content:disclosure_create"), {
            "title": "Công khai cơ sở vật chất", "section": section.pk, "description": "v1", "file": pdf_file(),
            "disclosure_date": "01/10/2026", "review_due": "01/11/2026", "version_note": "Lần đầu"})
        self.assertEqual(r.status_code, 302)
        d = Disclosure.objects.get()
        self.assertEqual(d.versions.count(), 1)
        self.client.post(reverse("content:disclosure_edit", args=[d.pk]), {
            "title": "Công khai cơ sở vật chất", "section": section.pk, "description": "v2", "version_note": "Cập nhật"})
        self.assertEqual(d.versions.count(), 2)
        # Văn phòng không có quyền xác nhận kiểm tra
        self.assertEqual(self.client.post(reverse("content:disclosure_check", args=[d.pk]), {"confirmed": "on"}).status_code, 403)
        self.login(self.principal)
        self.client.post(reverse("content:transition", args=["cong-khai", d.pk, "submit"]))
        self.client.post(reverse("content:transition", args=["cong-khai", d.pk, "approve"]))
        self.client.post(reverse("content:transition", args=["cong-khai", d.pk, "publish"]))
        d.refresh_from_db()
        self.assertEqual(d.status, Status.APPROVED)  # chưa xác nhận kiểm tra → không xuất bản
        self.client.post(reverse("content:disclosure_check", args=[d.pk]), {"confirmed": "on", "note": "Đã kiểm tra"})
        self.client.post(reverse("content:transition", args=["cong-khai", d.pk, "publish"]))
        d.refresh_from_db()
        self.assertEqual(d.status, Status.PUBLISHED)
        self.client.logout()
        r = self.client.get(reverse("public:disclosure_list"))
        self.assertContains(r, "Công khai cơ sở vật chất")
        self.assertEqual(self.client.get(reverse("public:disclosure_file", args=[d.pk])).status_code, 200)


class PublicDocumentTests(BaseTestCase):
    def test_download_only_published_and_counted(self):
        doc = PublicDocument(title="Đơn nhập học", category="bieu-mau", created_by=self.office)
        doc.file.save("don.pdf", pdf_file(), save=True)
        url = reverse("public:document_download", args=[doc.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        doc.status = Status.PUBLISHED
        doc.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        doc.refresh_from_db()
        self.assertEqual(doc.download_count, 1)

    def test_upload_rejects_disguised_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.login(self.office)
        bad = SimpleUploadedFile("hoso.pdf", b"MZ\x90\x00 executable", content_type="application/pdf")
        r = self.client.post(reverse("content:pubdoc_create"), {"title": "X", "category": "khac", "file": bad})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PublicDocument.objects.exists())
        exe = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        r = self.client.post(reverse("content:pubdoc_create"), {"title": "X", "category": "khac", "file": exe})
        self.assertFalse(PublicDocument.objects.exists())


class ContactFormTests(BaseTestCase):
    def _data(self, **kw):
        import time

        from django.core import signing

        data = {"name": "Phụ huynh", "email": "ph@example.com", "phone": "", "subject": "Hỏi tuyển sinh",
                "message": "Xin hỏi...", "agree": "on", "website": "", "ts": signing.dumps(time.time() - 10)}
        data.update(kw)
        return data

    def test_valid_submission(self):
        r = self.client.post(reverse("site:contact"), self._data())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_honeypot_and_speed_rejected(self):
        import time

        from django.core import signing

        self.client.post(reverse("site:contact"), self._data(website="http://spam"))
        self.client.post(reverse("site:contact"), self._data(ts=signing.dumps(time.time())))
        self.client.post(reverse("site:contact"), self._data(ts="gia-mao"))
        self.client.post(reverse("site:contact"), self._data(email="", phone=""))
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_home_and_public_pages_render(self):
        SiteSettings.load()
        for name in ("home", "about", "staff", "post_list", "announcement_list", "admission", "disclosure_list",
                     "album_list", "document_list", "search"):
            self.assertEqual(self.client.get(reverse(f"public:{name}")).status_code, 200, name)
