# Giai đoạn 1 — Phân tích yêu cầu, kiến trúc, sitemap, mô hình dữ liệu, phân quyền

> Tài liệu mô tả thiết kế **đã được hiện thực trong mã nguồn** của kho này. Hệ thống được xây dựng độc lập,
> không sao chép mã nguồn, dữ liệu, hình ảnh hay nhận diện thương hiệu của website tham khảo.
> Tôi (người xây dựng) không truy cập và không đối chiếu chi tiết website tham khảo; trải nghiệm được thiết kế dựa trên mô tả yêu cầu.

## 1. Phân tích yêu cầu

| Nhóm | Yêu cầu chính | Cách đáp ứng |
|---|---|---|
| Website công khai | Trang chủ, giới thiệu, tin tức, thông báo, công khai giáo dục, thư viện ảnh, tài liệu, liên hệ, tìm kiếm | App `content` (public views) + `core` (liên hệ) |
| Quản trị nội bộ | /quan-tri/: dashboard, nội dung, văn bản, kế hoạch, nhiệm vụ, minh chứng, báo cáo, cấu hình | Các app `core`, `content`, `office`, `reports`, `accounts`, `org` |
| Phân quyền | 7 vai trò, ma trận quyền cấu hình được, kiểm tra phía máy chủ, giới hạn phạm vi | `accounts.permissions` + `RolePermission` + queryset `for_user()` |
| Quy trình duyệt | Nháp → Chờ duyệt → Đã duyệt → Xuất bản → Ẩn/Lưu trữ | `core.workflow` (nội dung), quy trình riêng cho kế hoạch |
| Bảo vệ trẻ em | Không công khai ảnh trẻ khi chưa xác nhận đồng ý | `MediaItem.consent_status`, ảnh lưu kho nội bộ, chỉ phục vụ khi đủ điều kiện |
| AI tùy chọn | Chỉ hỗ trợ, không tự ban hành, không vượt quyền, không gửi dữ liệu nhạy cảm | App `ai_assistant`, mặc định tắt |
| Bảo mật | CSRF, lọc đầu vào, kiểm tra tệp, nhật ký, sao lưu, HTTPS | Xem `docs/04_BAO_MAT_VA_SU_CO.md` |

Giả định đã đặt ra (cần nhà trường xác nhận):
- Hệ thống **không** quản lý hồ sơ trẻ em/phụ huynh (không thu thập dữ liệu trẻ). Nếu mở rộng cần thiết kế riêng.
- Danh sách "mục công khai giáo dục" là **khung gợi ý cấu hình được**, chưa được đối chiếu với văn bản quy phạm hiện hành;
  người có thẩm quyền của trường phải rà soát.
- Một máy chủ (VPS) đơn, quy mô một trường (dưới vài trăm tài khoản).

## 2. Kiến trúc

```
Trình duyệt ──HTTPS──> Nginx ──(unix socket)──> Gunicorn ──> Django (config/*)
                       │  /static/  → staticfiles/                 │
                       │  /media/   → media/ (tệp công khai)       ├─ apps.accounts  (người dùng, vai trò, ma trận quyền, phiên)
                       │  /_protected/ (internal, X-Accel)         ├─ apps.org       (năm học, điểm trường, tổ, lớp, danh mục)
                       │     → protected_media/ (tệp nội bộ)       ├─ apps.core      (cấu hình, dashboard, nhật ký, nhắc việc, liên hệ, sao lưu)
                                                                    ├─ apps.content   (website công khai + quản trị nội dung)
PostgreSQL <────────────────────────────────────────────────────── ├─ apps.office    (văn bản, kế hoạch, nhiệm vụ, minh chứng)
                                                                    ├─ apps.reports   (thống kê, xuất Excel/PDF/Word)
Dịch vụ AI (tùy chọn, HTTPS) <──────────────────────────────────── └─ apps.ai_assistant (mặc định tắt)
```

Nguyên tắc:
- **Kiểm tra quyền 2 lớp**: (1) quyền chức năng theo ma trận `(vai trò, chức năng, thao tác)`; (2) phạm vi dữ liệu theo
  đối tượng (`for_user()`, `owns_or_scoped()`). Giao diện chỉ ẩn/hiện nút; máy chủ luôn kiểm tra lại.
- **Hai kho tệp**: `MEDIA_ROOT` (công khai: logo, ảnh đại diện bài viết) và `PROTECTED_MEDIA_ROOT` (văn bản, minh chứng, kế hoạch,
  ảnh album, tài liệu…) chỉ tải qua view có kiểm tra quyền.
- Cấu hình bí mật qua biến môi trường; tên trường/màu/logo/liên hệ sửa qua giao diện.

## 3. Sitemap

**Công khai**
- `/` Trang chủ · `/gioi-thieu/` · `/gioi-thieu/doi-ngu/` · `/trang/<slug>/`
- `/tin-tuc/` (tìm kiếm, lọc danh mục, phân trang) · `/tin-tuc/<slug>/`
- `/thong-bao/` (lọc loại) · `/thong-bao/<slug>/` · `/tuyen-sinh/`
- `/cong-khai/` · `/thu-vien-anh/` · `/thu-vien-anh/<slug>/` · `/tai-lieu/` · `/tim-kiem/` · `/lien-he/`
- `/tai-khoan/dang-nhap/`, `/tai-khoan/quen-mat-khau/`

**Quản trị (`/quan-tri/`)**
- Tổng quan · Nhắc việc · `noi-dung/` (tin-tuc, thong-bao, trang, doi-ngu, album, tai-lieu, cong-khai, muc-cong-khai, danh-muc-tin)
- `van-ban/` · `ke-hoach/` · `mau-xuat-ke-hoach/` · `nhiem-vu/` · `minh-chung/` · `danh-muc-minh-chung/`
- `bao-cao/` · `ai/` (AI hỗ trợ, tìm tài liệu nội bộ) · `tai-khoan/` · `tai-khoan/phan-quyen/` · `to-chuc/<loại>/`
- `cau-hinh/` · `nhat-ky/` · `lien-he/`

## 4. Mô hình dữ liệu (rút gọn)

| Nhóm | Bảng (model) | Ghi chú khóa/ràng buộc |
|---|---|---|
| Người dùng, vai trò | `accounts.User`, `RolePermission`, `LoginAttempt`, `UserSession` | unique(role, module, action); FK campus/group SET_NULL |
| Tổ chức | `org.SchoolYear`, `Campus`, `ProfessionalGroup`, `SchoolClass`, `Catalog` | unique(lớp, năm học, điểm trường); unique(kind, name) |
| Hồ sơ nhân sự (công khai) | `content.StaffProfile` | tách khỏi tài khoản; cờ đồng ý công khai |
| Tin tức | `content.Category`, `Post` | slug unique; index(status, published_at) |
| Thông báo | `content.Announcement` | thời hạn hiển thị start/end |
| Album, ảnh | `content.Album`, `MediaItem` | trạng thái quyền sử dụng hình ảnh, người xác nhận |
| Tài liệu, công khai | `content.PublicDocument`, `DisclosureSection`, `Disclosure`, `DisclosureVersion` | unique(disclosure, version_no) |
| Văn bản | `office.OfficialDocument` | index(direction, issue_date); phạm vi truy cập + người được chỉ định |
| Kế hoạch | `office.EducationPlan`, `PlanVersion`, `PlanComment`, `PlanExportTemplate` | unique(plan, version_no); cây parent |
| Nhiệm vụ | `office.Task`, `TaskComment`, `TaskAttachment` | giao cá nhân/tổ/điểm trường |
| Minh chứng | `office.EvidenceCategory`, `Evidence`, `EvidenceFile` | mã unique; unique(evidence, version_no) |
| Quy trình duyệt | trường `status/approved_by/approved_at/published_at` (WorkflowModel) | ghi nhật ký mỗi lần chuyển |
| Nhật ký | `core.AuditLog`, `Notification` | index(object_type, object_id), created_at |
| Cấu hình | `core.SiteSettings` (bản ghi duy nhất), `ContactMessage` | màu kiểm tra định dạng #RRGGBB |

Toàn bộ định nghĩa chi tiết nằm trong `apps/*/models.py` và migration `apps/*/migrations/`.

## 5. Ma trận phân quyền mặc định

Vai trò **Quản trị hệ thống** có toàn quyền (không hiển thị). HT = Hiệu trưởng, PHT = Phó Hiệu trưởng, VP = Nhân viên văn phòng,
TT = Tổ trưởng chuyên môn, GV = Giáo viên, NV = Nhân viên khác. Bảng sinh tự động từ `apps/accounts/permissions.py`;
có thể chỉnh tại `/quan-tri/tai-khoan/phan-quyen/` (chỉ Quản trị hệ thống).

| Chức năng | Thao tác | HT | PHT | VP | TT | GV | NV |
|---|---|---|---|---|---|---|---|
| Tin tức | Xem | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Tin tức | Tạo | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Tin tức | Sửa | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Tin tức | Xóa | ✔ | ✔ | – | – | – | – |
| Tin tức | Duyệt | ✔ | ✔ | – | – | – | – |
| Tin tức | Xuất bản | ✔ | ✔ | – | – | – | – |
| Thông báo | Xem | ✔ | ✔ | ✔ | ✔ | – | – |
| Thông báo | Tạo | ✔ | ✔ | ✔ | – | – | – |
| Thông báo | Sửa | ✔ | ✔ | ✔ | – | – | – |
| Thông báo | Xóa | ✔ | ✔ | – | – | – | – |
| Thông báo | Duyệt | ✔ | ✔ | – | – | – | – |
| Thông báo | Xuất bản | ✔ | ✔ | – | – | – | – |
| Trang giới thiệu | Xem | ✔ | ✔ | ✔ | – | – | – |
| Trang giới thiệu | Tạo | ✔ | ✔ | ✔ | – | – | – |
| Trang giới thiệu | Sửa | ✔ | ✔ | ✔ | – | – | – |
| Trang giới thiệu | Xóa | ✔ | ✔ | – | – | – | – |
| Trang giới thiệu | Xuất bản | ✔ | ✔ | – | – | – | – |
| Thư viện ảnh/video | Xem | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Thư viện ảnh/video | Tạo | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Thư viện ảnh/video | Sửa | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Thư viện ảnh/video | Xóa | ✔ | ✔ | – | – | – | – |
| Thư viện ảnh/video | Duyệt | ✔ | ✔ | – | – | – | – |
| Thư viện ảnh/video | Xuất bản | ✔ | ✔ | – | – | – | – |
| Tài liệu tải xuống công khai | Xem | ✔ | ✔ | ✔ | – | – | – |
| Tài liệu tải xuống công khai | Tạo | ✔ | ✔ | ✔ | – | – | – |
| Tài liệu tải xuống công khai | Sửa | ✔ | ✔ | ✔ | – | – | – |
| Tài liệu tải xuống công khai | Xóa | ✔ | ✔ | ✔ | – | – | – |
| Tài liệu tải xuống công khai | Xuất bản | ✔ | ✔ | ✔ | – | – | – |
| Công khai giáo dục | Xem | ✔ | ✔ | ✔ | – | – | – |
| Công khai giáo dục | Tạo | ✔ | ✔ | ✔ | – | – | – |
| Công khai giáo dục | Sửa | ✔ | ✔ | ✔ | – | – | – |
| Công khai giáo dục | Xóa | ✔ | – | – | – | – | – |
| Công khai giáo dục | Duyệt | ✔ | ✔ | – | – | – | – |
| Công khai giáo dục | Xuất bản | ✔ | – | – | – | – | – |
| Đội ngũ (hiển thị công khai) | Xem | ✔ | ✔ | ✔ | – | – | – |
| Đội ngũ (hiển thị công khai) | Tạo | ✔ | ✔ | ✔ | – | – | – |
| Đội ngũ (hiển thị công khai) | Sửa | ✔ | ✔ | ✔ | – | – | – |
| Đội ngũ (hiển thị công khai) | Xóa | ✔ | ✔ | ✔ | – | – | – |
| Quản lý văn bản | Xem | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Quản lý văn bản | Tạo | ✔ | ✔ | ✔ | – | – | – |
| Quản lý văn bản | Sửa | ✔ | ✔ | ✔ | – | – | – |
| Quản lý văn bản | Xóa | ✔ | – | ✔ | – | – | – |
| Quản lý văn bản | Tải xuống | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Quản lý văn bản | Xuất dữ liệu | ✔ | ✔ | ✔ | – | – | – |
| Kế hoạch giáo dục | Xem | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Kế hoạch giáo dục | Tạo | ✔ | ✔ | – | ✔ | ✔ | – |
| Kế hoạch giáo dục | Sửa | ✔ | ✔ | – | ✔ | ✔ | – |
| Kế hoạch giáo dục | Xóa | ✔ | ✔ | – | – | – | – |
| Kế hoạch giáo dục | Duyệt | ✔ | ✔ | – | ✔ | – | – |
| Kế hoạch giáo dục | Tải xuống | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Kế hoạch giáo dục | Xuất dữ liệu | ✔ | ✔ | – | ✔ | – | – |
| Nhiệm vụ | Xem | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Nhiệm vụ | Tạo | ✔ | ✔ | – | ✔ | – | – |
| Nhiệm vụ | Sửa | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Nhiệm vụ | Xóa | ✔ | ✔ | – | – | – | – |
| Nhiệm vụ | Duyệt | ✔ | ✔ | – | ✔ | – | – |
| Nhiệm vụ | Xuất dữ liệu | ✔ | ✔ | – | – | – | – |
| Minh chứng | Xem | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Minh chứng | Tạo | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Minh chứng | Sửa | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Minh chứng | Xóa | ✔ | ✔ | – | – | – | – |
| Minh chứng | Tải xuống | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| Minh chứng | Xuất dữ liệu | ✔ | ✔ | ✔ | – | – | – |
| Báo cáo, thống kê | Xem | ✔ | ✔ | ✔ | ✔ | – | – |
| Báo cáo, thống kê | Xuất dữ liệu | ✔ | ✔ | – | – | – | – |
| Tài khoản người dùng | Xem | ✔ | ✔ | ✔ | – | – | – |
| Tài khoản người dùng | Tạo | ✔ | – | – | – | – | – |
| Tài khoản người dùng | Sửa | ✔ | – | – | – | – | – |
| Tài khoản người dùng | Xóa | – | – | – | – | – | – |
| Cơ cấu tổ chức, danh mục | Xem | ✔ | ✔ | ✔ | ✔ | – | – |
| Cơ cấu tổ chức, danh mục | Tạo | ✔ | – | ✔ | – | – | – |
| Cơ cấu tổ chức, danh mục | Sửa | ✔ | – | ✔ | – | – | – |
| Cơ cấu tổ chức, danh mục | Xóa | ✔ | – | – | – | – | – |
| Cấu hình hệ thống | Xem | ✔ | ✔ | – | – | – | – |
| Cấu hình hệ thống | Sửa | ✔ | – | – | – | – | – |
| Nhật ký hệ thống | Xem | ✔ | – | – | – | – | – |
| Nhật ký hệ thống | Xuất dữ liệu | ✔ | – | – | – | – | – |
| Liên hệ từ phụ huynh | Xem | ✔ | ✔ | ✔ | – | – | – |
| Liên hệ từ phụ huynh | Xóa | ✔ | – | ✔ | – | – | – |
| AI hỗ trợ | Sử dụng | ✔ | ✔ | ✔ | ✔ | ✔ | – |

**Giới hạn phạm vi dữ liệu (ngoài ma trận):**
- HT, PHT, VP, Quản trị: phạm vi toàn trường.
- TT: dữ liệu của mình + của tổ (nội dung có gắn tổ, kế hoạch của tổ, nhiệm vụ giao cho tổ). Chỉ duyệt kế hoạch cấp tổ/lớp của tổ mình; không duyệt kế hoạch cấp trường; chỉ giao việc trong tổ.
- GV, NV: dữ liệu do mình tạo/được giao; kế hoạch của lớp mình phụ trách; kế hoạch tổ đã đưa ra góp ý/đã duyệt; kế hoạch trường đã duyệt.
- Văn bản: `Toàn bộ` / `Lãnh đạo và văn phòng` / `Chỉ người được chỉ định` (+ người tạo, người phụ trách, HT, Quản trị).
- Minh chứng: phạm vi theo tổ/điểm trường + mức truy cập.
- Ma trận và phạm vi được kiểm thử tự động: `apps/core/tests/test_url_matrix.py` và các test theo chức năng.
