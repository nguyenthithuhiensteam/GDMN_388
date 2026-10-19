# Website quản trị trường mầm non

Hệ thống gồm **website công khai** (phụ huynh, cộng đồng) và **khu quản trị nội bộ** `/quan-tri/` (lãnh đạo, văn phòng, giáo viên),
xây dựng bằng Python Django. Tên trường mặc định: `TRƯỜNG MẦM NON [TÊN TRƯỜNG]` — đổi tên, logo, màu, liên hệ trong giao diện Cấu hình.
Ngôn ngữ tiếng Việt, múi giờ Asia/Ho_Chi_Minh, ngày dd/mm/yyyy.

> Mã nguồn được viết độc lập; không sao chép mã, dữ liệu, hình ảnh hay thương hiệu của website khác.

## Cài đặt trên Windows 10/11 (máy tính cá nhân, môi trường phát triển)

1. Cài **Python 3.11 trở lên** từ https://www.python.org/downloads/windows/ — khi cài, tích chọn **"Add python.exe to PATH"**.
   (Đã kiểm thử với Python 3.13; các phiên bản 3.11–3.12 dự kiến tương thích nhưng chưa chạy thử.)
2. Giải nén tệp ZIP mã nguồn, ví dụ vào `C:\mamnon`. Mở **PowerShell** tại thư mục đó (Shift + chuột phải → *Open PowerShell window here*).
3. Chạy lần lượt:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   # Nếu báo lỗi "running scripts is disabled": chạy lệnh dưới rồi kích hoạt lại
   #   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py create_admin --username quantri --email ban@truong.edu.vn
   python manage.py runserver
   ```
   Lệnh `create_admin` hỏi mật khẩu (gõ không hiển thị, tối thiểu 10 ký tự, không quá phổ biến).
4. Mở trình duyệt: http://127.0.0.1:8000/ (website) và http://127.0.0.1:8000/quan-tri/ (quản trị).
5. (Tùy chọn) dữ liệu MẪU để dùng thử: `python manage.py seed_demo` — mật khẩu các tài khoản mẫu chỉ in ra **một lần**;
   xóa bằng `python manage.py seed_demo --remove`.
6. Lần sau: mở PowerShell tại thư mục dự án → `.\.venv\Scripts\Activate.ps1` → `python manage.py runserver`.

Ghi chú Windows: môi trường phát triển dùng SQLite (tệp `db.sqlite3`), không cần cài PostgreSQL. `requirements.txt` chỉ gồm
các gói chạy được trên Windows; gói dành cho máy chủ (Gunicorn, PostgreSQL) nằm riêng trong `requirements-prod.txt`.
Tôi chưa chạy thử các bước này trên máy Windows thật (mới kiểm thử trên Linux).

Trên macOS/Linux: thay `py` bằng `python3` và `.\.venv\Scripts\Activate.ps1` bằng `source .venv/bin/activate`.

### Kiểm tra mã nguồn
```bash
python manage.py test          # 98 kiểm thử tự động
python manage.py check
pip install ruff && ruff check . && ruff format --check .
```

## Triển khai lên máy chủ (tóm tắt)
Hướng dẫn đầy đủ: [docs/02_CAI_DAT_VA_TRIEN_KHAI.md](docs/02_CAI_DAT_VA_TRIEN_KHAI.md). Tóm tắt trên VPS Ubuntu:

1. Trỏ DNS: bản ghi `A` của tên miền (và `www`) về IP máy chủ.
2. Cài gói: `python3-venv postgresql nginx certbot python3-certbot-nginx`; tạo người dùng hệ thống `mamnon`, CSDL PostgreSQL `mamnon`.
3. Lấy mã nguồn vào `/srv/mamnon/app`, tạo venv, `pip install -r requirements-prod.txt`.
4. `cp .env.example .env`, điền `DJANGO_SECRET_KEY`, mật khẩu CSDL, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, SMTP; `chmod 600 .env`.
5. `python manage.py migrate && python manage.py collectstatic --noinput && python manage.py check --deploy`.
6. `python manage.py create_admin --username ...` (không chạy `seed_demo` trên máy chủ chính thức).
7. Cài `deploy/mamnon.service` (Gunicorn), `deploy/mamnon-daily.timer` (sao lưu, nhắc việc, dọn dữ liệu), `deploy/nginx.conf`.
8. HTTPS: `sudo certbot --nginx -d ten-mien -d www.ten-mien`.
9. Xác minh: `curl -I https://ten-mien/` trả 200, đăng nhập `/quan-tri/` được, `python manage.py verify_backup <tệp> --restore-test` thành công.

> **Trạng thái triển khai Internet:** chưa thực hiện. Môi trường làm việc hiện tại không có máy chủ, tên miền hay thông tin
> xác thực của nhà trường. Khi có VPS (IP, quyền SSH), tên miền và tài khoản SMTP, có thể thực hiện các bước trên.

## Tài liệu
| Tệp | Nội dung |
|---|---|
| [docs/01_PHAN_TICH_THIET_KE.md](docs/01_PHAN_TICH_THIET_KE.md) | Phân tích yêu cầu, kiến trúc, sitemap, mô hình dữ liệu, ma trận phân quyền |
| [docs/02_CAI_DAT_VA_TRIEN_KHAI.md](docs/02_CAI_DAT_VA_TRIEN_KHAI.md) | Cài đặt máy tính; VPS, DNS, PostgreSQL, Gunicorn, Nginx, HTTPS, sao lưu, giám sát, nâng cấp, khôi phục |
| [docs/03_HUONG_DAN_QUAN_TRI.md](docs/03_HUONG_DAN_QUAN_TRI.md) | Hướng dẫn quản trị, phân quyền và các quy trình nghiệp vụ |
| [docs/04_BAO_MAT_VA_SU_CO.md](docs/04_BAO_MAT_VA_SU_CO.md) | Biện pháp bảo mật, chính sách lưu giữ dữ liệu, xử lý sự cố |
| [docs/05_TRANG_THAI_CHUC_NANG.md](docs/05_TRANG_THAI_CHUC_NANG.md) | Đã hoàn thành / chưa hoàn thành / hạn chế |
| [docs/06_BAO_CAO_GIAI_DOAN_1_2.md](docs/06_BAO_CAO_GIAI_DOAN_1_2.md) | Báo cáo rà soát và kết quả kiểm tra Giai đoạn 1–2 |

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
