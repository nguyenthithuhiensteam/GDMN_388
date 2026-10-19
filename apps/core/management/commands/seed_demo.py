"""Dữ liệu MẪU để dùng thử/đào tạo. Mọi bản ghi có tiền tố [MẪU] hoặc tài khoản bắt đầu bằng "mau_",
và được gỡ bỏ bằng: python manage.py seed_demo --remove

Không chạy trên môi trường chính thức (trừ khi chủ động dùng --force cho môi trường đào tạo)."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

TAG = "[MẪU]"
USER_PREFIX = "mau_"


class Command(BaseCommand):
    help = "Tạo hoặc xóa dữ liệu mẫu (được đánh dấu rõ ràng)."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Xóa toàn bộ dữ liệu mẫu.")
        parser.add_argument("--force", action="store_true", help="Cho phép chạy khi DJANGO_ENV=production.")

    def handle(self, *args, **opts):
        if settings.IS_PRODUCTION and not opts["force"]:
            raise CommandError("Không tạo/xóa dữ liệu mẫu trên môi trường chính thức (dùng --force nếu là bản đào tạo).")
        if opts["remove"]:
            self.remove()
        else:
            self.create()

    @transaction.atomic
    def remove(self):
        from apps.accounts.models import User
        from apps.content.models import Album, Announcement, Disclosure, Page, Post, PublicDocument, StaffProfile
        from apps.core.models import SiteSettings
        from apps.office.models import EducationPlan, Evidence, EvidenceCategory, OfficialDocument, Task
        from apps.org.models import Campus, ProfessionalGroup, SchoolClass, SchoolYear

        Evidence.objects.filter(title__startswith=TAG).delete()
        EvidenceCategory.objects.filter(name__startswith=TAG).delete()
        Task.objects.filter(title__startswith=TAG).delete()
        EducationPlan.objects.filter(title__startswith=TAG).delete()
        OfficialDocument.objects.filter(summary__startswith=TAG).delete()
        for m in (Post, Announcement, Page, Album, PublicDocument, Disclosure):
            m.objects.filter(title__startswith=TAG).delete()
        StaffProfile.objects.filter(full_name__startswith=TAG).delete()
        User.objects.filter(username__startswith=USER_PREFIX).delete()
        SchoolClass.objects.filter(name__startswith=TAG).delete()
        ProfessionalGroup.objects.filter(name__startswith=TAG).delete()
        Campus.objects.filter(name__startswith=TAG).delete()
        SchoolYear.objects.filter(name__startswith="MAU-").delete()
        s = SiteSettings.load()
        s.demo_data_loaded = False
        s.save()
        self.stdout.write(self.style.SUCCESS("Đã xóa dữ liệu mẫu."))

    @transaction.atomic
    def create(self):
        from apps.accounts.models import User
        from apps.accounts.permissions import (
            ROLE_GROUP_LEADER, ROLE_OFFICE, ROLE_PRINCIPAL, ROLE_STAFF, ROLE_TEACHER, ROLE_VICE,
        )
        from apps.content.models import Announcement, Category, Page, Post, StaffProfile
        from apps.core.models import SiteSettings
        from apps.core.workflow import Status
        from apps.office.models import EducationPlan, Evidence, EvidenceCategory, OfficialDocument, Task
        from apps.org.models import Campus, Catalog, ProfessionalGroup, SchoolClass, SchoolYear

        if User.objects.filter(username__startswith=USER_PREFIX).exists():
            raise CommandError("Dữ liệu mẫu đã tồn tại. Chạy --remove trước nếu muốn tạo lại.")
        today = timezone.localdate()
        year = SchoolYear.objects.create(name=f"MAU-{today.year}-{today.year + 1}", start_date=today.replace(month=9, day=1)
                                         if today.month >= 8 else today.replace(year=today.year - 1, month=9, day=1),
                                         end_date=today + timedelta(days=270), is_current=not SchoolYear.objects.exists())
        main = Campus.objects.create(name=f"{TAG} Điểm trường chính", code="mau-chinh", is_main=True, address="Địa chỉ mẫu")
        branch = Campus.objects.create(name=f"{TAG} Điểm trường lẻ", code="mau-le", address="Địa chỉ mẫu 2", order=1)
        g1 = ProfessionalGroup.objects.create(name=f"{TAG} Tổ Mẫu giáo lớn", code="mau-mgl")
        g2 = ProfessionalGroup.objects.create(name=f"{TAG} Tổ Nhà trẻ", code="mau-nt")
        c1 = SchoolClass.objects.create(name=f"{TAG} Lớp 5 tuổi A", school_year=year, campus=main, group=g1, age_group="5_6")
        SchoolClass.objects.create(name=f"{TAG} Lớp 24-36 tháng", school_year=year, campus=branch, group=g2, age_group="nha_tre")

        passwords = {}

        def mk(username, full_name, role, **kw):
            pw = secrets.token_urlsafe(10)
            u = User(username=USER_PREFIX + username, full_name=f"{TAG} {full_name}", role=role, **kw)
            u.set_password(pw)
            u.save()
            passwords[u.username] = pw
            return u

        principal = mk("hieutruong", "Hiệu trưởng", ROLE_PRINCIPAL, campus=main)
        vice = mk("phohieutruong", "Phó Hiệu trưởng", ROLE_VICE, campus=main)
        mk("vanphong", "Nhân viên văn phòng", ROLE_OFFICE, campus=main)
        leader = mk("totruong", "Tổ trưởng MGL", ROLE_GROUP_LEADER, campus=main, group=g1)
        teacher = mk("giaovien", "Giáo viên lớp 5 tuổi A", ROLE_TEACHER, campus=main, group=g1)
        teacher.classes.add(c1)
        mk("nhanvien", "Nhân viên y tế", ROLE_STAFF, campus=main)

        cat = Category.objects.first()
        now = timezone.now()
        for i in range(1, 8):
            Post.objects.create(
                title=f"{TAG} Hoạt động trải nghiệm số {i}", category=cat, summary="Nội dung minh họa, không phải tin thật.",
                body="<p>Đây là bài viết <strong>mẫu</strong> để thử nghiệm giao diện và quy trình duyệt.</p>",
                status=Status.PUBLISHED if i < 6 else Status.PENDING, is_featured=i <= 3, created_by=teacher,
                approved_by=vice, approved_at=now, published_at=now - timedelta(days=i) if i < 6 else None,
            )
        for kind in ("school", "admission", "schedule", "urgent"):
            Announcement.objects.create(
                title=f"{TAG} Thông báo ({dict(Announcement.KINDS)[kind]})", kind=kind,
                body="<p>Thông báo minh họa, không có giá trị thực tế.</p>", status=Status.PUBLISHED,
                published_at=now, start_date=today, end_date=today + timedelta(days=30), created_by=vice, approved_by=vice,
            )
        for section, title in (("lich-su", "Lịch sử hình thành"), ("su-menh", "Sứ mệnh, tầm nhìn"),
                               ("co-so-vat-chat", "Cơ sở vật chất"), ("chuong-trinh", "Chương trình giáo dục")):
            Page.objects.create(title=f"{TAG} {title}", section=section, status=Status.PUBLISHED, published_at=now,
                                body="<p>Nội dung mẫu; nhà trường thay bằng nội dung thật.</p>", created_by=vice)
        StaffProfile.objects.create(full_name=f"{TAG} Nguyễn Văn A", position="Hiệu trưởng", staff_group="bgh", public_consent=True)
        StaffProfile.objects.create(full_name=f"{TAG} Trần Thị B", position="Giáo viên", staff_group="gv", public_consent=True)

        doc_type = Catalog.objects.filter(kind="doc_type").first()
        for i in range(1, 4):
            OfficialDocument.objects.create(
                direction="in", number=str(100 + i), symbol="MAU", issue_date=today - timedelta(days=i * 3),
                issuer_text="Cơ quan mẫu", doc_type=doc_type, summary=f"{TAG} Văn bản minh họa số {i}",
                content_text="Nội dung minh họa.", responsible=vice, deadline=today + timedelta(days=i * 5 - 8),
                processing_status="processing", created_by=principal,
            )
        plan = EducationPlan.objects.create(
            title=f"{TAG} Kế hoạch chủ đề Gia đình", level="theme", school_year=year, group=g1, school_class=c1,
            content="I. Mục tiêu\n...\nII. Nội dung\n...\nIII. Hoạt động\n...", status="consulting", created_by=teacher,
        )
        from apps.office.models import PlanVersion

        PlanVersion.objects.create(plan=plan, version_no=1, title=plan.title, content=plan.content, status="draft",
                                   note="Tạo mới (mẫu)", created_by=teacher)
        Task.objects.create(title=f"{TAG} Chuẩn bị hồ sơ chuyên đề", assignee=teacher, due_date=today + timedelta(days=3),
                            created_by=leader, description="Nhiệm vụ minh họa.")
        Task.objects.create(title=f"{TAG} Rà soát kế hoạch tổ", assigned_group=g1, due_date=today - timedelta(days=1),
                            created_by=vice, status="in_progress")
        ec = EvidenceCategory.objects.create(code="MAU-1", name=f"{TAG} Tiêu chí 1: Tổ chức và quản lý")
        Evidence.objects.create(code="MAU-1.1", title=f"{TAG} Quyết định thành lập tổ chuyên môn", category=ec,
                                responsible=vice, school_year=year, created_by=vice)

        s = SiteSettings.load()
        s.demo_data_loaded = True
        s.save()
        self.stdout.write(self.style.WARNING("Đã tạo DỮ LIỆU MẪU. Tài khoản mẫu (mật khẩu ngẫu nhiên, chỉ hiển thị một lần):"))
        for u, p in passwords.items():
            self.stdout.write(f"  {u}: {p}")
        self.stdout.write("Xóa dữ liệu mẫu: python manage.py seed_demo --remove")
