# Website quản trị trường mầm non

Hệ thống gồm **website công khai** (phụ huynh, cộng đồng) và **khu quản trị nội bộ** `/quan-tri/` (lãnh đạo, văn phòng, giáo viên),
xây dựng bằng Python Django. Tên trường mặc định: `TRƯỜNG MẦM NON [TÊN TRƯỜNG]` — đổi tên, logo, màu, liên hệ trong giao diện Cấu hình.
Ngôn ngữ tiếng Việt, múi giờ Asia/Ho_Chi_Minh, ngày dd/mm/yyyy.

> Mã nguồn được viết độc lập; không sao chép mã, dữ liệu, hình ảnh hay thương hiệu của website khác.

## Chạy nhanh trên máy tính
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py create_admin --username quantri      # nhập mật khẩu ẩn (≥10 ký tự)
python manage.py seed_demo                             # tùy chọn: dữ liệu MẪU [MẪU], in mật khẩu tài khoản mẫu
python manage.py runserver
```
- Website: http://127.0.0.1:8000/ · Quản trị: http://127.0.0.1:8000/quan-tri/
- Kiểm thử: `python manage.py test` · Xóa dữ liệu mẫu: `python manage.py seed_demo --remove`

## Tài liệu
| Tệp | Nội dung |
|---|---|
| [docs/01_PHAN_TICH_THIET_KE.md](docs/01_PHAN_TICH_THIET_KE.md) | Phân tích yêu cầu, kiến trúc, sitemap, mô hình dữ liệu, ma trận phân quyền |
| [docs/02_CAI_DAT_VA_TRIEN_KHAI.md](docs/02_CAI_DAT_VA_TRIEN_KHAI.md) | Cài đặt máy tính; VPS, DNS, PostgreSQL, Gunicorn, Nginx, HTTPS, sao lưu, giám sát, nâng cấp, khôi phục |
| [docs/03_HUONG_DAN_QUAN_TRI.md](docs/03_HUONG_DAN_QUAN_TRI.md) | Hướng dẫn quản trị, phân quyền và các quy trình nghiệp vụ |
| [docs/04_BAO_MAT_VA_SU_CO.md](docs/04_BAO_MAT_VA_SU_CO.md) | Biện pháp bảo mật, chính sách lưu giữ dữ liệu, xử lý sự cố |
| [docs/05_TRANG_THAI_CHUC_NANG.md](docs/05_TRANG_THAI_CHUC_NANG.md) | Đã hoàn thành / chưa hoàn thành / hạn chế |

## Cấu trúc thư mục
```
config/                 settings.py (đọc biến môi trường), urls.py, wsgi.py, asgi.py
apps/accounts/          Tài khoản, 7 vai trò, ma trận quyền (permissions.py), khóa đăng nhập, phiên, quản lý người dùng
apps/org/               Năm học, điểm trường, tổ chuyên môn, lớp, danh mục chuyên môn
apps/core/              Cấu hình trường, dashboard, nhật ký, nhắc việc, liên hệ, quy trình duyệt (workflow.py),
                        khung CRUD có kiểm tra quyền (crud.py), kiểm tra tệp (validators.py), kho tệp nội bộ (storage.py),
                        làm sạch HTML (sanitize.py), lệnh quản trị (management/commands/)
apps/content/           Tin tức, thông báo, trang giới thiệu, đội ngũ, album ảnh/video, tài liệu, công khai giáo dục
                        (views_public.py = website; views_admin.py = quản trị)
apps/office/            Văn bản, kế hoạch giáo dục (phiên bản, góp ý, duyệt, xuất Word/PDF), nhiệm vụ, minh chứng
apps/reports/           Báo cáo thống kê, xuất Excel/PDF/Word (exporters.py, font DejaVu hỗ trợ tiếng Việt)
apps/ai_assistant/      AI hỗ trợ tùy chọn (service.py), tìm kiếm tài liệu nội bộ theo quyền
templates/              Giao diện (base_public.html, base_admin.html, các trang theo app)
static/                 CSS/JS riêng + Bootstrap 5.3.3, Bootstrap Icons 1.11.3 (đóng gói sẵn, không cần CDN)
deploy/                 nginx.conf, gunicorn.conf.py, systemd service/timer, backup.sh
docs/                   Tài liệu
```
Mỗi app có `tests/` chứa kiểm thử tự động.

## Lệnh quản trị
| Lệnh | Mục đích |
|---|---|
| `create_admin --username U [--email E]` | Tạo tài khoản Quản trị hệ thống, mật khẩu nhập ẩn |
| `seed_demo` / `seed_demo --remove` | Tạo / xóa dữ liệu MẪU (bị chặn ở production) |
| `backup_data` | Sao lưu CSDL (JSON) + tệp vào ZIP có SHA-256 |
| `verify_backup FILE [--restore-test]` | Kiểm tra toàn vẹn; khôi phục thử vào CSDL tạm |
| `restore_data FILE --yes` | Khôi phục vào CSDL mới |
| `send_reminders` | Nhắc việc sắp/quá hạn, hạn rà soát công khai |
| `cleanup_data [--dry-run]` | Xóa dữ liệu hết thời hạn lưu giữ |

## Cấu hình
Sao chép `.env.example` → `.env` và điền giá trị. Không đưa `.env`, mật khẩu hay khóa API vào Git.
Mô-đun AI mặc định tắt; bật bằng `AI_ENABLED=True` + `ANTHROPIC_API_KEY` + `pip install -r requirements-ai.txt`.

## Giấy phép thành phần bên thứ ba
Bootstrap, Bootstrap Icons (MIT — `static/vendor/*/LICENSE`); font DejaVu (`apps/reports/fonts/LICENSE-DejaVu.txt`).
